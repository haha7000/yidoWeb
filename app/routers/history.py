from fastapi import APIRouter, Request, HTTPException, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, RedirectResponse
from app.core.database import SessionLocal
from app.models.models import User, Receipt, Passport, ReceiptMatchLog, ShillaReceipt, ProcessingHistory, PassportArchive
from datetime import datetime
from sqlalchemy.sql import text
from sqlalchemy.orm import Session
from app.core.auth import get_current_user, get_db
from app.core.config import settings

router = APIRouter()
templates = Jinja2Templates(directory=settings.templates_dir)

@router.post("/complete-session/")
async def complete_session(
    request: Request,
    session_name: str = Form(""),
    save_to_history: bool = Form(True),  # 기본값을 True로 변경
    current_user: User = Depends(get_current_user)
):
    """
    현재 세션 완료 및 데이터 초기화
    이력에 저장하고 현재 세션 초기화
    """
    # 새로운 데이터베이스 세션 생성
    db = SessionLocal()
    
    try:
        print(f"세션 완료 요청: 사용자={current_user.id}, 세션명='{session_name}'")
        
        # 1. 현재 처리 데이터 확인
        current_data = db.query(ReceiptMatchLog).filter(
            ReceiptMatchLog.user_id == current_user.id
        ).all()
        
        if not current_data:
            print("처리할 데이터가 없음")
            db.close()
            return RedirectResponse(url="/upload/?completed=true", status_code=302)
        
        # 2. 세션명 설정
        if session_name.strip():
            final_session_name = session_name.strip()
        else:
            final_session_name = f"세션_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        print(f"세션명: {final_session_name}")
        print(f"처리할 레코드 수: {len(current_data)}")
        
        # 3. 현재 데이터를 ProcessingHistory 테이블로 이동 (개별 처리로 변경)
        print("이력 저장 시작...")
        
        # 모든 레코드에 대해 동일한 upload_id 사용
        common_upload_id = None
        for record in current_data:
            if record.upload_id:
                common_upload_id = record.upload_id
                break
        
        # 공통 upload_id가 없으면 새로 생성 (한 번만)
        if not common_upload_id:
            common_upload_id = f"legacy_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        print(f"사용할 upload_id: {common_upload_id}")
        
        saved_count = 0
        for i, record in enumerate(current_data):
            try:
                print(f"레코드 {i+1}/{len(current_data)} 처리 중: {record.receipt_number}")
                
                # 모든 레코드에 동일한 upload_id 사용
                upload_id = common_upload_id
                
                history_record = ProcessingHistory(
                    user_id=record.user_id,
                    upload_id=upload_id,
                    session_name=final_session_name,
                    receipt_number=record.receipt_number,
                    is_matched=record.is_matched,
                    excel_name=record.excel_name,
                    passport_number=record.passport_number,
                    birthday=record.birthday,
                    sales_date=record.sales_date,
                    category=record.category,
                    brand=record.brand,
                    product_code=record.product_code,
                    discount_amount_krw=record.discount_amount_krw,
                    sales_price_usd=record.sales_price_usd,
                    net_sales_krw=record.net_sales_krw,
                    store_branch=record.store_branch,
                    discount_rate=record.discount_rate,
                    commission_fee=record.commission_fee,
                    duty_free_type=record.duty_free_type,
                    processed_at=record.checked_at or datetime.now()
                )
                
                db.add(history_record)
                db.flush()  # 개별 플러시로 문제 지점 확인
                saved_count += 1
                print(f"레코드 {i+1} 저장 완료")
                
            except Exception as record_error:
                print(f"레코드 {i+1} 저장 중 오류: {record_error}")
                print(f"문제 레코드: receipt_number={record.receipt_number}, user_id={record.user_id}")
                raise record_error
        
        print(f"이력 레코드 {saved_count}개 저장 완료")
        
        # 4. 현재 세션 데이터 초기화
        print("현재 세션 데이터 초기화...")
        
        # 4-1. 여권 데이터를 아카이브로 복사
        print("여권 데이터 아카이브 저장 시작...")
        passports_to_archive = db.query(Passport).filter(
            Passport.user_id == current_user.id
        ).all()
        
        archived_passport_count = 0
        for passport in passports_to_archive:
            try:
                archived_passport = PassportArchive(
                    user_id=passport.user_id,
                    upload_id=passport.upload_id,
                    session_name=final_session_name,
                    original_passport_id=passport.id,
                    file_path=passport.file_path,
                    passport_number=passport.passport_number,
                    birthday=passport.birthday,
                    name=passport.name,
                    is_matched=passport.is_matched,
                    original_created_at=passport.created_at
                )
                db.add(archived_passport)
                archived_passport_count += 1
                print(f"여권 아카이브 저장: {passport.passport_number}")
            except Exception as archive_error:
                print(f"여권 아카이브 저장 오류: {archive_error}")
                
        print(f"여권 아카이브 {archived_passport_count}개 저장 완료")
        
        # 4-2. receipt_match_log 테이블 초기화
        deleted_count = db.query(ReceiptMatchLog).filter(
            ReceiptMatchLog.user_id == current_user.id
        ).delete()
        print(f"receipt_match_log {deleted_count}개 삭제")
        
        # 4-3. 다른 테이블들도 초기화
        receipt_deleted = db.query(Receipt).filter(Receipt.user_id == current_user.id).delete()
        shilla_deleted = db.query(ShillaReceipt).filter(ShillaReceipt.user_id == current_user.id).delete()
        passport_deleted = db.query(Passport).filter(Passport.user_id == current_user.id).delete()
        
        print(f"기타 테이블 삭제: receipts={receipt_deleted}, shilla_receipts={shilla_deleted}, passports={passport_deleted}")
        print(f"아카이브된 여권: {archived_passport_count}개")
        
        # 엑셀 데이터 테이블은 보존 (다른 사용자도 사용할 수 있으므로)
        # 엑셀 데이터는 업로드 시마다 새로 생성되므로 삭제하지 않음
        print("엑셀 데이터 테이블은 보존됨 (다른 사용자와 공유 가능)")
        
        # 모든 변경사항 커밋
        db.commit()
        print("세션 완료 및 초기화 성공")
        
        # 이력 페이지로 리다이렉트
        return RedirectResponse(url="/history/", status_code=302)
            
    except Exception as e:
        print(f"세션 완료 처리 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # 롤백 처리
        try:
            db.rollback()
        except Exception as rollback_error:
            print(f"롤백 중 오류: {rollback_error}")
        
        # 에러 페이지 반환
        from app.services.matching import fetch_results
        try:
            matched, unmatched = fetch_results(current_user.id, "shilla")
        except:
            matched, unmatched = [], []
            
        return templates.TemplateResponse("result.html", {
            "request": request,
            "user": current_user,
            "error": f"처리 중 오류가 발생했습니다: {str(e)}",
            "results": matched,
            "unmatched_receipts": unmatched,
            "duty_free_type": "shilla"
        })
    finally:
        # 데이터베이스 세션 닫기
        try:
            db.close()
        except Exception as close_error:
            print(f"DB 세션 닫기 중 오류: {close_error}")

@router.get("/history/")
async def processing_history(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """처리 이력 조회 페이지"""
    try:
        # ProcessingHistory에서 세션별 요약 정보 조회 (duty_free_type 그룹핑 제거)
        history_summary = db.execute(text("""
            WITH session_duty_free AS (
                SELECT 
                    upload_id,
                    session_name,
                    user_id,
                    duty_free_type,
                    COUNT(*) as type_count,
                    ROW_NUMBER() OVER (
                        PARTITION BY upload_id, session_name, user_id 
                        ORDER BY COUNT(*) DESC, duty_free_type DESC
                    ) as rn
                FROM processing_history 
                WHERE user_id = :user_id
                GROUP BY upload_id, session_name, user_id, duty_free_type
            )
            SELECT 
                p.upload_id,
                p.session_name,
                sdf.duty_free_type,
                MIN(p.archived_at) as session_date,
                COUNT(*) as total_records,
                COUNT(CASE WHEN p.is_matched = true THEN 1 END) as matched_records,
                SUM(CASE WHEN p.commission_fee IS NOT NULL THEN p.commission_fee ELSE 0 END) as total_commission
            FROM processing_history p
            JOIN session_duty_free sdf ON p.upload_id = sdf.upload_id 
                AND p.session_name = sdf.session_name 
                AND p.user_id = sdf.user_id 
                AND sdf.rn = 1
            WHERE p.user_id = :user_id 
            GROUP BY p.upload_id, p.session_name, sdf.duty_free_type
            ORDER BY MIN(p.archived_at) DESC
        """), {"user_id": current_user.id}).fetchall()
        
        # 결과를 딕셔너리로 변환
        sessions = []
        for row in history_summary:
            completion_rate = (row.matched_records / row.total_records * 100) if row.total_records > 0 else 0
            sessions.append({
                'upload_id': row.upload_id,
                'session_name': row.session_name,
                'duty_free_type': row.duty_free_type,
                'session_date': row.session_date,
                'total_records': row.total_records,
                'matched_records': row.matched_records,
                'completion_rate': round(completion_rate, 1),
                'total_commission': float(row.total_commission) if row.total_commission else 0
            })
        
        return templates.TemplateResponse("history.html", {
            "request": request,
            "user": current_user,
            "sessions": sessions
        })
        
    except Exception as e:
        print(f"이력 조회 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return templates.TemplateResponse("history.html", {
            "request": request,
            "user": current_user,
            "error": f"이력 조회 중 오류가 발생했습니다: {str(e)}",
            "sessions": []
        })

@router.get("/history/search/")
async def search_history(
    request: Request,
    q: str = "",
    search_type: str = "all",  # all, customer, passport, receipt
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """이력 검색 API"""
    try:
        if not q.strip():
            return {
                "success": True,
                "results": [],
                "total": 0
            }
        
        # 검색 타입에 따른 WHERE 조건 설정
        search_conditions = []
        params = {"user_id": current_user.id, "query": f"%{q.strip()}%"}
        
        if search_type == "customer" or search_type == "all":
            search_conditions.append("excel_name ILIKE :query")
        
        if search_type == "passport" or search_type == "all":
            search_conditions.append("passport_number ILIKE :query")
        
        if search_type == "receipt" or search_type == "all":
            search_conditions.append("receipt_number ILIKE :query")
        
        if search_type == "all":
            search_conditions.extend([
                "brand ILIKE :query",
                "category ILIKE :query",
                "session_name ILIKE :query"
            ])
        
        where_clause = " OR ".join(search_conditions) if search_conditions else "1=0"
        
        # 검색 쿼리 실행
        search_query = text(f"""
            SELECT 
                upload_id,
                session_name,
                receipt_number,
                excel_name,
                passport_number,
                brand,
                category,
                duty_free_type,
                is_matched,
                commission_fee,
                net_sales_krw,
                archived_at
            FROM processing_history 
            WHERE user_id = :user_id AND ({where_clause})
            ORDER BY archived_at DESC
            LIMIT 100
        """)
        
        search_results = db.execute(search_query, params).fetchall()
        
        # 결과를 딕셔너리로 변환
        results = []
        for row in search_results:
            results.append({
                'upload_id': row.upload_id,
                'session_name': row.session_name,
                'receipt_number': row.receipt_number,
                'excel_name': row.excel_name,
                'passport_number': row.passport_number,
                'brand': row.brand,
                'category': row.category,
                'duty_free_type': row.duty_free_type,
                'is_matched': row.is_matched,
                'commission_fee': float(row.commission_fee) if row.commission_fee else 0,
                'net_sales_krw': float(row.net_sales_krw) if row.net_sales_krw else 0,
                'archived_at': row.archived_at.strftime('%Y-%m-%d %H:%M:%S') if row.archived_at else ''
            })
        
        return {
            "success": True,
            "results": results,
            "total": len(results)
        }
        
    except Exception as e:
        print(f"이력 검색 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "results": [],
            "total": 0
        }

@router.get("/history/session-detail/{upload_id}")
async def get_session_detail(
    upload_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """세션 상세 정보 조회"""
    try:
        # 특정 업로드 ID의 모든 레코드 조회
        detail_query = text("""
            SELECT 
                receipt_number,
                excel_name,
                passport_number,
                brand,
                category,
                is_matched,
                commission_fee,
                net_sales_krw,
                discount_rate,
                sales_date,
                processed_at,
                duty_free_type
            FROM processing_history 
            WHERE user_id = :user_id AND upload_id = :upload_id
            ORDER BY processed_at DESC
        """)
        
        detail_results = db.execute(detail_query, {
            "user_id": current_user.id,
            "upload_id": upload_id
        }).fetchall()
        
        # 결과를 딕셔너리로 변환
        details = []
        for row in detail_results:
            details.append({
                'receipt_number': row.receipt_number,
                'excel_name': row.excel_name,
                'passport_number': row.passport_number,
                'brand': row.brand,
                'category': row.category,
                'is_matched': row.is_matched,
                'commission_fee': float(row.commission_fee) if row.commission_fee else 0,
                'net_sales_krw': float(row.net_sales_krw) if row.net_sales_krw else 0,
                'discount_rate': float(row.discount_rate) if row.discount_rate else 0,
                'sales_date': row.sales_date.strftime('%Y-%m-%d') if row.sales_date else '',
                'processed_at': row.processed_at.strftime('%Y-%m-%d %H:%M:%S') if row.processed_at else '',
                'duty_free_type': row.duty_free_type
            })
        
        return {
            "success": True,
            "data": details
        }
        
    except Exception as e:
        print(f"세션 상세 조회 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }

@router.delete("/history/delete-session/{upload_id}")
async def delete_session(
    upload_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """세션 삭제"""
    try:
        # 해당 업로드 ID의 모든 레코드 삭제
        deleted_count = db.execute(text("""
            DELETE FROM processing_history 
            WHERE user_id = :user_id AND upload_id = :upload_id
        """), {
            "user_id": current_user.id,
            "upload_id": upload_id
        }).rowcount
        
        db.commit()
        
        if deleted_count > 0:
            print(f"세션 삭제 완료: upload_id={upload_id}, 삭제된 레코드={deleted_count}")
            return {
                "success": True,
                "message": f"{deleted_count}개의 레코드가 삭제되었습니다."
            }
        else:
            return {
                "success": False,
                "error": "삭제할 데이터를 찾을 수 없습니다."
            }
        
    except Exception as e:
        print(f"세션 삭제 오류: {str(e)}")
        db.rollback()
        return {
            "success": False,
            "error": str(e)
        }