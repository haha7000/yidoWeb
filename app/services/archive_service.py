# app/services/archive_service.py - 수정된 버전

from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.models import ProcessingArchive, MatchingHistory
from datetime import datetime
import json

class ArchiveService:
    """아카이브 및 이력 관리 서비스"""
    
    def save_current_session_to_history(self, user_id: int, session_name: str):
        """현재 세션을 이력에 저장"""
        with SessionLocal() as db:
            try:
                print(f"사용자 {user_id}의 세션 '{session_name}' 이력 저장 시작...")
                
                # 1. 현재 세션 통계 수집
                stats = self._collect_session_statistics(user_id, db)
                print(f"수집된 통계: {stats}")
                
                if stats["total_receipts"] == 0:
                    print("저장할 데이터가 없습니다.")
                    return False
                
                # 2. 아카이브 레코드 생성
                archive = ProcessingArchive(
                    user_id=user_id,
                    session_name=session_name,
                    total_receipts=stats["total_receipts"],
                    matched_receipts=stats["matched_receipts"],
                    total_passports=stats["total_passports"],
                    matched_passports=stats["matched_passports"],
                    duty_free_type=stats["duty_free_type"],
                    archive_data=stats["detailed_data"]
                )
                db.add(archive)
                db.flush()  # ID 생성
                print(f"아카이브 레코드 생성 완료 (ID: {archive.id})")
                
                # 3. 상세 매칭 이력 저장
                detail_count = self._save_detailed_matching_history(user_id, archive.id, db, stats["duty_free_type"])
                print(f"상세 이력 저장 완료: {detail_count}개")
                
                db.commit()
                print(f"세션 '{session_name}' 이력 저장 완료!")
                return True
                
            except Exception as e:
                db.rollback()
                print(f"이력 저장 오류: {e}")
                import traceback
                traceback.print_exc()
                return False
    
    def _collect_session_statistics(self, user_id: int, db):
        """현재 세션 통계 수집"""
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
            
            duty_free_type = "shilla" if shilla_count >= lotte_count else "lotte"
            print(f"통계 수집: 신라={shilla_count}, 롯데={lotte_count}, 타입={duty_free_type}")
            
            if duty_free_type == "shilla":
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
                
                # 상세 데이터도 수집
                detail_sql = """
                SELECT 
                    sr.id as receipt_id,
                    sr.receipt_number,
                    sr.passport_number as receipt_passport,
                    se.name as excel_name,
                    se.passport_number as excel_passport,
                    CASE WHEN se."receiptNumber" IS NOT NULL THEN true ELSE false END as matched
                FROM shilla_receipts sr
                LEFT JOIN shilla_excel_data se ON se."receiptNumber"::text = sr.receipt_number
                WHERE sr.user_id = :user_id
                ORDER BY sr.receipt_number
                """
            else:
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
                
                detail_sql = """
                SELECT 
                    r.id as receipt_id,
                    r.receipt_number,
                    '' as receipt_passport,
                    rml.excel_name,
                    rml.passport_number as excel_passport,
                    COALESCE(rml.is_matched, false) as matched
                FROM receipts r
                LEFT JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number AND rml.user_id = r.user_id
                WHERE r.user_id = :user_id
                ORDER BY r.receipt_number
                """
            
            # 기본 통계 수집
            result = db.execute(text(stats_sql), {"user_id": user_id}).first()
            
            # 상세 영수증 데이터 수집
            receipt_details = db.execute(text(detail_sql), {"user_id": user_id}).fetchall()
            receipt_data = []
            for row in receipt_details:
                receipt_data.append({
                    'receipt_id': row[0],
                    'receipt_number': row[1],
                    'receipt_passport': row[2],
                    'excel_name': row[3],
                    'excel_passport': row[4],
                    'matched': row[5]
                })
            
            # 여권 데이터 수집
            passport_sql = """
            SELECT id, name, passport_number, birthday, is_matched
            FROM passports 
            WHERE user_id = :user_id
            ORDER BY name
            """
            passport_details = db.execute(text(passport_sql), {"user_id": user_id}).fetchall()
            passport_data = []
            for row in passport_details:
                passport_data.append({
                    'passport_id': row[0],
                    'name': row[1],
                    'passport_number': row[2],
                    'birthday': row[3].isoformat() if row[3] else None,
                    'is_matched': row[4]
                })
            
            return {
                "total_receipts": result[0] or 0,
                "matched_receipts": result[1] or 0,
                "total_passports": result[2] or 0,
                "matched_passports": result[3] or 0,
                "duty_free_type": duty_free_type,
                "detailed_data": {
                    "receipts": receipt_data,
                    "passports": passport_data,
                    "archived_at": datetime.now().isoformat(),
                    "duty_free_type": duty_free_type
                }
            }
            
        except Exception as e:
            print(f"통계 수집 오류: {e}")
            import traceback
            traceback.print_exc()
            return {
                "total_receipts": 0, "matched_receipts": 0,
                "total_passports": 0, "matched_passports": 0,
                "duty_free_type": "unknown", "detailed_data": {}
            }
    
    def _save_detailed_matching_history(self, user_id: int, archive_id: int, db, duty_free_type: str):
        """상세 매칭 이력 저장"""
        try:
            print(f"상세 이력 저장 시작 (타입: {duty_free_type})")
            
            if duty_free_type == "shilla":
                # 신라 매칭 결과 조회
                history_sql = """
                SELECT DISTINCT
                    COALESCE(p.name, se.name) as customer_name,
                    COALESCE(sr.passport_number, se.passport_number) as passport_number,
                    sr.receipt_number,
                    se.name as excel_name,
                    p.name as passport_name,
                    p.birthday,
                    CASE WHEN se."receiptNumber" IS NOT NULL THEN 'matched' ELSE 'unmatched' END as match_status
                FROM shilla_receipts sr
                LEFT JOIN shilla_excel_data se ON se."receiptNumber"::text = sr.receipt_number
                LEFT JOIN passports p ON COALESCE(sr.passport_number, se.passport_number) = p.passport_number 
                                       AND p.user_id = :user_id
                WHERE sr.user_id = :user_id
                AND se."receiptNumber" IS NOT NULL  -- 매칭된 것만
                ORDER BY customer_name
                """
            else:
                # 롯데 매칭 결과 조회
                history_sql = """
                SELECT DISTINCT
                    COALESCE(p.name, rml.excel_name) as customer_name,
                    rml.passport_number,
                    rml.receipt_number,
                    rml.excel_name,
                    p.name as passport_name,
                    p.birthday,
                    CASE WHEN rml.is_matched = TRUE THEN 'matched' ELSE 'unmatched' END as match_status
                FROM receipt_match_log rml
                LEFT JOIN passports p ON rml.passport_number = p.passport_number AND p.user_id = :user_id
                WHERE rml.user_id = :user_id
                AND rml.is_matched = TRUE  -- 매칭된 것만
                ORDER BY customer_name
                """
            
            history_results = db.execute(text(history_sql), {"user_id": user_id}).fetchall()
            
            # 고객별로 그룹화하여 저장
            customer_groups = {}
            for row in history_results:
                customer_name = row[0] or '알 수 없음'
                passport_number = row[1]
                receipt_number = row[2]
                excel_name = row[3]
                passport_name = row[4]
                birthday = row[5]
                match_status = row[6]
                
                # 고객별 그룹화 키
                group_key = f"{customer_name}_{passport_number}" if passport_number else f"{customer_name}_no_passport"
                
                if group_key not in customer_groups:
                    customer_groups[group_key] = {
                        'customer_name': customer_name,
                        'passport_number': passport_number,
                        'receipt_numbers': [],
                        'excel_data': {
                            'excel_name': excel_name,
                            'passport_name': passport_name,
                            'birthday': birthday.isoformat() if birthday else None,
                            'duty_free_type': duty_free_type
                        },
                        'match_status': match_status
                    }
                
                customer_groups[group_key]['receipt_numbers'].append(receipt_number)
            
            # 각 그룹별로 MatchingHistory 레코드 생성
            saved_count = 0
            for group_data in customer_groups.values():
                history = MatchingHistory(
                    user_id=user_id,
                    archive_id=archive_id,
                    customer_name=group_data['customer_name'],
                    passport_number=group_data['passport_number'],
                    receipt_numbers=json.dumps(group_data['receipt_numbers']),
                    excel_data=group_data['excel_data'],
                    match_status=group_data['match_status']
                )
                db.add(history)
                saved_count += 1
                print(f"이력 저장: {group_data['customer_name']} - {len(group_data['receipt_numbers'])}건")
            
            return saved_count
                
        except Exception as e:
            print(f"상세 이력 저장 오류: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def get_user_archives(self, user_id: int, limit: int = 50):
        """사용자 아카이브 목록 조회"""
        with SessionLocal() as db:
            try:
                archives_sql = """
                SELECT 
                    id, session_name, archive_date,
                    total_receipts, matched_receipts,
                    total_passports, matched_passports,
                    duty_free_type, notes
                FROM processing_archives
                WHERE user_id = :user_id
                ORDER BY archive_date DESC
                LIMIT :limit
                """
                
                results = db.execute(text(archives_sql), {
                    "user_id": user_id, 
                    "limit": limit
                }).fetchall()
                
                archives = []
                for row in results:
                    completion_rate = round((row[4] / row[3] * 100) if row[3] > 0 else 0, 1)
                    archives.append({
                        "id": row[0],
                        "session_name": row[1],
                        "archive_date": row[2],
                        "total_receipts": row[3],
                        "matched_receipts": row[4],
                        "total_passports": row[5],
                        "matched_passports": row[6],
                        "duty_free_type": row[7] or "unknown",
                        "notes": row[8],
                        "completion_rate": completion_rate
                    })
                
                print(f"사용자 {user_id}의 아카이브 조회: {len(archives)}개")
                return archives
                
            except Exception as e:
                print(f"아카이브 조회 오류: {e}")
                import traceback
                traceback.print_exc()
                return []
    
    def search_matching_history(self, user_id: int, query: str, search_type: str = "all"):
        """매칭 이력 검색"""
        with SessionLocal() as db:
            try:
                base_sql = """
                SELECT 
                    mh.id, mh.customer_name, mh.passport_number,
                    mh.receipt_numbers, mh.excel_data, mh.match_status,
                    mh.created_at, pa.session_name, pa.archive_date
                FROM matching_history mh
                LEFT JOIN processing_archives pa ON mh.archive_id = pa.id
                WHERE mh.user_id = :user_id
                """
                
                params = {"user_id": user_id, "query": f"%{query}%"}
                
                if search_type == "customer":
                    base_sql += " AND mh.customer_name ILIKE :query"
                elif search_type == "passport":
                    base_sql += " AND mh.passport_number ILIKE :query"
                elif search_type == "receipt":
                    base_sql += " AND mh.receipt_numbers ILIKE :query"
                else:  # search_type == "all"
                    base_sql += """ AND (
                        mh.customer_name ILIKE :query OR 
                        mh.passport_number ILIKE :query OR 
                        mh.receipt_numbers ILIKE :query
                    )"""
                
                base_sql += " ORDER BY mh.created_at DESC LIMIT 100"
                
                results = db.execute(text(base_sql), params).fetchall()
                
                search_results = []
                for row in results:
                    search_results.append({
                        "id": row[0],
                        "customer_name": row[1],
                        "passport_number": row[2],
                        "receipt_numbers": json.loads(row[3]) if row[3] else [],
                        "excel_data": row[4] or {},
                        "match_status": row[5],
                        "created_at": row[6],
                        "session_name": row[7],
                        "archive_date": row[8]
                    })
                
                return search_results
                
            except Exception as e:
                print(f"이력 검색 오류: {e}")
                return []