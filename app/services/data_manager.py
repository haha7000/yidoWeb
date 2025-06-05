# app/services/data_manager.py - 수정된 버전
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.models import Receipt, Passport, ReceiptMatchLog, UnrecognizedImage, ShillaReceipt
from datetime import datetime

class DataManager:
    """사용자별 데이터 관리 클래스"""
    
    @staticmethod
    def get_user_statistics(user_id: int):
        """사용자별 현재 처리 상태 통계 - 자동 면세점 타입 감지"""
        with SessionLocal() as db:
            try:
                # 신라와 롯데 데이터 모두 확인하여 실제 사용 중인 타입 결정
                shilla_count_sql = text("SELECT COUNT(*) FROM shilla_receipts WHERE user_id = :user_id")
                lotte_count_sql = text("SELECT COUNT(*) FROM receipts WHERE user_id = :user_id")
                
                try:
                    shilla_count = db.execute(shilla_count_sql, {"user_id": user_id}).scalar() or 0
                except:
                    shilla_count = 0
                    
                try:
                    lotte_count = db.execute(lotte_count_sql, {"user_id": user_id}).scalar() or 0
                except:
                    lotte_count = 0
                
                # 더 많은 데이터가 있는 쪽을 주 타입으로 결정
                duty_free_type = "shilla" if shilla_count >= lotte_count else "lotte"
                
                print(f"사용자 {user_id} 통계 조회: 신라={shilla_count}, 롯데={lotte_count}, 선택된 타입={duty_free_type}")
                
                if duty_free_type == "shilla":
                    # 신라 데이터 통계
                    stats_sql = """
                    SELECT 
                        COUNT(DISTINCT sr.id) as total_receipts,
                        COUNT(DISTINCT CASE WHEN se."receiptNumber" IS NOT NULL THEN sr.id END) as matched_receipts,
                        COUNT(DISTINCT p.id) as total_passports,
                        COUNT(DISTINCT CASE WHEN p.is_matched = TRUE THEN p.id END) as matched_passports
                    FROM shilla_receipts sr
                    LEFT JOIN shilla_excel_data se ON se."receiptNumber"::text = sr.receipt_number
                    LEFT JOIN passports p ON p.user_id = sr.user_id
                    WHERE sr.user_id = :user_id
                    """
                else:
                    # 롯데 데이터 통계
                    stats_sql = """
                    SELECT 
                        COUNT(DISTINCT r.id) as total_receipts,
                        COUNT(DISTINCT CASE WHEN rml.is_matched = TRUE THEN r.id END) as matched_receipts,
                        COUNT(DISTINCT p.id) as total_passports,
                        COUNT(DISTINCT CASE WHEN p.is_matched = TRUE THEN p.id END) as matched_passports
                    FROM receipts r
                    LEFT JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number AND rml.user_id = r.user_id
                    LEFT JOIN passports p ON p.user_id = r.user_id
                    WHERE r.user_id = :user_id
                    """
                
                result = db.execute(text(stats_sql), {"user_id": user_id}).first()
                
                if result:
                    return {
                        "total_receipts": result[0] or 0,
                        "matched_receipts": result[1] or 0,
                        "total_passports": result[2] or 0,
                        "matched_passports": result[3] or 0,
                        "unmatched_receipts": (result[0] or 0) - (result[1] or 0),
                        "unmatched_passports": (result[2] or 0) - (result[3] or 0),
                        "duty_free_type": duty_free_type
                    }
                else:
                    return {
                        "total_receipts": 0, "matched_receipts": 0,
                        "total_passports": 0, "matched_passports": 0,
                        "unmatched_receipts": 0, "unmatched_passports": 0,
                        "duty_free_type": duty_free_type
                    }
                    
            except Exception as e:
                print(f"통계 조회 오류: {e}")
                return {
                    "total_receipts": 0, "matched_receipts": 0,
                    "total_passports": 0, "matched_passports": 0,
                    "unmatched_receipts": 0, "unmatched_passports": 0,
                    "duty_free_type": "lotte"
                }
    
    @staticmethod
    def clear_current_session_data(user_id: int):
        """현재 세션의 모든 데이터 삭제 (엑셀 데이터는 유지)"""
        with SessionLocal() as db:
            try:
                print(f"사용자 {user_id}의 세션 데이터 삭제 시작...")
                
                # 1. 매칭 로그 삭제
                deleted_logs = db.query(ReceiptMatchLog).filter(ReceiptMatchLog.user_id == user_id).delete()
                print(f"매칭 로그 삭제: {deleted_logs}개")
                
                # 2. 영수증 데이터 삭제
                deleted_receipts = db.query(Receipt).filter(Receipt.user_id == user_id).delete()
                print(f"롯데 영수증 삭제: {deleted_receipts}개")
                
                deleted_shilla_receipts = db.query(ShillaReceipt).filter(ShillaReceipt.user_id == user_id).delete()
                print(f"신라 영수증 삭제: {deleted_shilla_receipts}개")
                
                # 3. 여권 데이터 삭제
                deleted_passports = db.query(Passport).filter(Passport.user_id == user_id).delete()
                print(f"여권 데이터 삭제: {deleted_passports}개")
                
                # 4. 인식되지 않은 이미지 삭제
                deleted_images = db.query(UnrecognizedImage).filter(UnrecognizedImage.user_id == user_id).delete()
                print(f"인식되지 않은 이미지 삭제: {deleted_images}개")
                
                # 5. 엑셀 데이터에서 여권번호 초기화 (신라만)
                try:
                    reset_shilla_sql = """
                    UPDATE shilla_excel_data 
                    SET passport_number = NULL 
                    WHERE passport_number IS NOT NULL
                    """
                    reset_result = db.execute(text(reset_shilla_sql))
                    print(f"신라 엑셀 데이터 여권번호 초기화: {reset_result.rowcount}개")
                except Exception as e:
                    print(f"신라 엑셀 데이터 초기화 오류 (테이블 없을 수 있음): {e}")
                
                db.commit()
                print(f"사용자 {user_id}의 세션 데이터 삭제 완료")
                return True
                
            except Exception as e:
                db.rollback()
                print(f"데이터 초기화 오류: {e}")
                return False