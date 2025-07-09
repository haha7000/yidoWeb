from fastapi import APIRouter, Request, HTTPException, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, JSONResponse
import os, shutil
from app.core.database import SessionLocal
from app.models.models import User, Receipt, Passport, ReceiptMatchLog, ShillaReceipt
from app.services.receipt_service import ReceiptService
from app.utils.helpers import safe_float
from datetime import datetime
from sqlalchemy.sql import text
from sqlalchemy.orm import Session
from app.core.auth import get_current_user, get_db
from app.core.config import settings

router = APIRouter()
templates = Jinja2Templates(directory=settings.templates_dir)

@router.get("/generate-receipts/")
async def generate_receipts(
    request: Request, 
    current_user: User = Depends(get_current_user)
):
    try:
        print(f"사용자 {current_user.id}의 수령증 생성 시작...")
        
        # ReceiptService를 사용하여 현재 세션의 수령증 생성
        receipt_service = ReceiptService()
        zip_path = receipt_service.generate_receipts_for_current_session(current_user.id)
        
        if not zip_path or not os.path.exists(zip_path):
            raise Exception("생성된 수령증이 없습니다. 매칭된 데이터를 확인해주세요.")
        
        print(f"수령증 ZIP 파일 생성 완료: {zip_path}")
        
        # 파일 다운로드 후 임시 파일 삭제를 위한 백그라운드 태스크
        def cleanup_temp_file():
            try:
                temp_dir = os.path.dirname(zip_path)
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    print(f"임시 파일 삭제 완료: {temp_dir}")
            except Exception as e:
                print(f"임시 파일 삭제 오류: {e}")
        
        # 파일 응답 반환
        response = FileResponse(
            path=zip_path, 
            filename="수령증_모음.zip",
            media_type="application/zip"
        )
        
        # 다운로드 후 파일 삭제 (백그라운드에서)
        import threading
        threading.Timer(10.0, cleanup_temp_file).start()  # 10초 후 삭제
        
        return response
        
    except Exception as e:
        print(f"수령증 생성 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"수령증 생성 중 오류가 발생했습니다: {str(e)}")

@router.get("/edit_unmatched/{receipt_id}")
async def edit_unmatched(
    request: Request, 
    receipt_id: int,
    current_user: User = Depends(get_current_user)
):
    db = SessionLocal()
    try:
        # 먼저 일반 영수증에서 확인
        receipt = db.query(Receipt).filter(
            Receipt.id == receipt_id,
            Receipt.user_id == current_user.id
        ).first()
        
        if receipt:
            # 롯데 면세점 영수증
            return templates.TemplateResponse(
                "edit_unmatched.html",
                {
                    "request": request,
                    "receipt": receipt,
                    "user": current_user,
                    "duty_free_type": "lotte"
                }
            )
        
        # 신라 영수증에서 확인
        shilla_receipt = db.query(ShillaReceipt).filter(
            ShillaReceipt.id == receipt_id,
            ShillaReceipt.user_id == current_user.id
        ).first()
        
        if shilla_receipt:
            # 매칭 가능한 여권 목록 조회 (매칭되지 않은 여권들)
            available_passports_sql = text("""
                SELECT DISTINCT p.name, p.passport_number, p.birthday
                FROM passports p
                WHERE p.user_id = :user_id
                AND (
                    p.is_matched = FALSE 
                    OR p.passport_number NOT IN (
                        SELECT DISTINCT sr.passport_number 
                        FROM shilla_receipts sr 
                        WHERE sr.passport_number IS NOT NULL 
                        AND sr.user_id = :user_id
                    )
                )
                ORDER BY p.name
            """)
            available_passports = db.execute(available_passports_sql, {"user_id": current_user.id}).fetchall()
            
            return templates.TemplateResponse(
                "edit_unmatched.html",
                {
                    "request": request,
                    "receipt": shilla_receipt,
                    "available_passports": available_passports,
                    "user": current_user,
                    "duty_free_type": "shilla"
                }
            )
        
        raise HTTPException(status_code=404, detail="영수증을 찾을 수 없습니다.")
        
    finally:
        db.close()

@router.post("/edit_unmatched/{receipt_id}")
async def update_unmatched(
    receipt_id: int, 
    new_receipt_number: str = Form(...),
    passport_number: str = Form(""),  # 신라 면세점용 추가 필드
    current_user: User = Depends(get_current_user)
):
    db = SessionLocal()
    try:
        # 먼저 일반 영수증에서 확인
        receipt = db.query(Receipt).filter(
            Receipt.id == receipt_id,
            Receipt.user_id == current_user.id
        ).first()
        
        if receipt:
            # 롯데 면세점 처리
            old_receipt_number = receipt.receipt_number
            receipt.receipt_number = new_receipt_number
            
            # 롯데 엑셀 데이터에서 검색 (상세 정보 포함)
            sql = text("""
                SELECT "receiptNumber", name, "PayBack",
                       "매출일자" as sales_date,
                       "카테고리" as category,
                       "브랜드" as brand,
                       "상품코드" as product_code,
                       "할인액(\)" as discount_amount_krw,
                       "판매가($)" as sales_price_usd,
                       "순매출액(\)" as net_sales_krw,
                       "점구분" as store_branch
                FROM lotte_excel_data
                WHERE "receiptNumber" = :receipt_number
            """)
            result = db.execute(sql, {"receipt_number": new_receipt_number}).first()
            
            # 매칭 로그 업데이트 (상세 정보 포함)
            match_log = db.query(ReceiptMatchLog).filter(
                ReceiptMatchLog.receipt_number == old_receipt_number,
                ReceiptMatchLog.user_id == current_user.id
            ).first()
            
            if match_log:
                match_log.receipt_number = new_receipt_number
                match_log.is_matched = result is not None
                match_log.excel_name = result[1] if result else None
                
                # 여권 정보도 추가 (엑셀 이름으로 여권 검색)
                if result and result[1]:
                    passport_info = db.query(Passport).filter(
                        Passport.name == result[1],
                        Passport.user_id == current_user.id
                    ).first()
                    if passport_info:
                        match_log.passport_number = passport_info.passport_number
                        match_log.birthday = passport_info.birthday
                
                # 엑셀 상세 정보 업데이트
                if result:
                    # 날짜 변환 처리
                    parsed_sales_date = None
                    if result[3]:  # sales_date
                        try:
                            if isinstance(result[3], str):
                                parsed_sales_date = datetime.strptime(result[3], '%Y-%m-%d').date()
                            elif hasattr(result[3], 'date'):
                                parsed_sales_date = result[3].date()
                            else:
                                parsed_sales_date = result[3]
                        except (ValueError, AttributeError) as e:
                            print(f"날짜 파싱 오류: {result[3]} - {e}")
                            parsed_sales_date = None
                    
                    # safe_float 함수는 app.utils.helpers에서 import됨
                    
                    match_log.sales_date = parsed_sales_date
                    match_log.category = result[4]  # category
                    match_log.brand = result[5]  # brand
                    match_log.product_code = result[6]  # product_code
                    match_log.discount_amount_krw = safe_float(result[7])  # discount_amount_krw
                    match_log.sales_price_usd = safe_float(result[8])  # sales_price_usd
                    match_log.net_sales_krw = safe_float(result[9])  # net_sales_krw
                    match_log.store_branch = result[10]  # store_branch
            else:
                # 새 로그 생성 시에도 상세 정보 포함
                passport_info = None
                if result and result[1]:
                    passport_info = db.query(Passport).filter(
                        Passport.name == result[1],
                        Passport.user_id == current_user.id
                    ).first()
                
                # 날짜 변환 처리
                parsed_sales_date = None
                if result and result[3]:  # sales_date
                    try:
                        if isinstance(result[3], str):
                            parsed_sales_date = datetime.strptime(result[3], '%Y-%m-%d').date()
                        elif hasattr(result[3], 'date'):
                            parsed_sales_date = result[3].date()
                        else:
                            parsed_sales_date = result[3]
                    except (ValueError, AttributeError) as e:
                        print(f"날짜 파싱 오류: {result[3]} - {e}")
                        parsed_sales_date = None
                
                # safe_float 함수는 app.utils.helpers에서 import됨
                    
                new_match_log = ReceiptMatchLog(
                    user_id=current_user.id,
                    receipt_number=new_receipt_number,
                    is_matched=result is not None,
                    excel_name=result[1] if result else None,
                    passport_number=passport_info.passport_number if passport_info else None,
                    birthday=passport_info.birthday if passport_info else None,
                    # 엑셀 상세 정보
                    sales_date=parsed_sales_date if result else None,
                    category=result[4] if result else None,
                    brand=result[5] if result else None,
                    product_code=result[6] if result else None,
                    discount_amount_krw=safe_float(result[7]) if result else None,
                    sales_price_usd=safe_float(result[8]) if result else None,
                    net_sales_krw=safe_float(result[9]) if result else None,
                    store_branch=result[10] if result else None
                )
                db.add(new_match_log)
                    
            db.commit()
            
            # 매칭 성공 여부 확인
            is_matched = result is not None
            
            # 다음 매칭되지 않은 영수증 찾기
            unmatched_sql = text("""
                SELECT r.id, r.receipt_number, r.file_path
                FROM receipts r
                JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number
                WHERE rml.is_matched = FALSE 
                AND r.user_id = :user_id 
                AND rml.user_id = :user_id
                AND r.id > :current_id
                ORDER BY r.id
                LIMIT 1
            """)
            next_receipt = db.execute(unmatched_sql, {"user_id": current_user.id, "current_id": receipt_id}).fetchone()
            
            # JSON 응답으로 결과 반환
            return {
                "success": True,
                "matched": is_matched,
                "message": "매칭 성공" if is_matched else "매칭 실패 - 엑셀 데이터에서 해당 영수증 번호를 찾을 수 없습니다",
                "next_receipt": {
                    "id": next_receipt.id,
                    "receipt_number": next_receipt.receipt_number
                } if next_receipt else None,
                "has_more": next_receipt is not None
            }
        
        # 신라 영수증 처리
        shilla_receipt = db.query(ShillaReceipt).filter(
            ShillaReceipt.id == receipt_id,
            ShillaReceipt.user_id == current_user.id
        ).first()
        
        if not shilla_receipt:
            raise HTTPException(status_code=404, detail="영수증을 찾을 수 없습니다.")
        
        old_receipt_number = shilla_receipt.receipt_number
        old_passport_number = shilla_receipt.passport_number
        
        # 영수증 정보 업데이트
        shilla_receipt.receipt_number = new_receipt_number
        if passport_number.strip():  # 여권번호가 제공된 경우에만 업데이트
            shilla_receipt.passport_number = passport_number.strip()
        
        # 신라 엑셀 데이터에서 영수증 번호 매칭 확인 (상세 정보 포함)
        excel_sql = text("""
            SELECT "receiptNumber", name, "PayBack",
                   "매출일자" as sales_date,
                   "카테고리" as category,
                   "브랜드명" as brand,
                   "상품코드" as product_code,
                   "할인액(￦)" as discount_amount_krw,
                   "판매가($)" as sales_price_usd,
                   "순매출액(￦)" as net_sales_krw,
                   "점" as store_branch
            FROM shilla_excel_data
            WHERE "receiptNumber"::text = :receipt_number
        """)
        excel_result = db.execute(excel_sql, {"receipt_number": new_receipt_number}).first()
        
        # 여권 정보 매칭 (여권번호가 제공된 경우)
        passport_info = None
        if passport_number.strip():
            passport_info = db.query(Passport).filter(
                Passport.passport_number == passport_number.strip(),
                Passport.user_id == current_user.id
            ).first()
            
            if passport_info:
                # 여권 매칭 상태 업데이트
                passport_info.is_matched = True
                
                # 이전 여권이 있었다면 매칭 해제
                if old_passport_number and old_passport_number != passport_number.strip():
                    old_passport = db.query(Passport).filter(
                        Passport.passport_number == old_passport_number,
                        Passport.user_id == current_user.id
                    ).first()
                    if old_passport:
                        old_passport.is_matched = False
        
        # 매칭 로그 업데이트
        match_log = db.query(ReceiptMatchLog).filter(
            ReceiptMatchLog.receipt_number == old_receipt_number,
            ReceiptMatchLog.user_id == current_user.id
        ).first()
        
        if match_log:
            # 기존 로그 업데이트 (상세 정보 포함)
            match_log.receipt_number = new_receipt_number
            match_log.is_matched = excel_result is not None
            match_log.excel_name = excel_result[1] if excel_result else None
            match_log.passport_number = passport_number.strip() if passport_number.strip() else None
            match_log.birthday = passport_info.birthday if passport_info else None
            
            # 엑셀 상세 정보 업데이트
            if excel_result:
                # 날짜 변환 처리
                parsed_sales_date = None
                if excel_result[3]:  # sales_date
                    try:
                        if isinstance(excel_result[3], str):
                            parsed_sales_date = datetime.strptime(excel_result[3], '%Y-%m-%d').date()
                        elif hasattr(excel_result[3], 'date'):
                            parsed_sales_date = excel_result[3].date()
                        else:
                            parsed_sales_date = excel_result[3]
                    except (ValueError, AttributeError) as e:
                        print(f"날짜 파싱 오류: {excel_result[3]} - {e}")
                        parsed_sales_date = None
                
                # safe_float 함수는 app.utils.helpers에서 import됨
                
                match_log.sales_date = parsed_sales_date
                match_log.category = excel_result[4]  # category
                match_log.brand = excel_result[5]  # brand
                match_log.product_code = excel_result[6]  # product_code
                match_log.discount_amount_krw = safe_float(excel_result[7])  # discount_amount_krw
                match_log.sales_price_usd = safe_float(excel_result[8])  # sales_price_usd
                match_log.net_sales_krw = safe_float(excel_result[9])  # net_sales_krw
                match_log.store_branch = excel_result[10]  # store_branch
        else:
            # 새 로그 생성 (상세 정보 포함)
            # 날짜 변환 처리
            parsed_sales_date = None
            if excel_result and excel_result[3]:  # sales_date
                try:
                    if isinstance(excel_result[3], str):
                        parsed_sales_date = datetime.strptime(excel_result[3], '%Y-%m-%d').date()
                    elif hasattr(excel_result[3], 'date'):
                        parsed_sales_date = excel_result[3].date()
                    else:
                        parsed_sales_date = excel_result[3]
                except (ValueError, AttributeError) as e:
                    print(f"날짜 파싱 오류: {excel_result[3]} - {e}")
                    parsed_sales_date = None
            
            # safe_float 함수는 app.utils.helpers에서 import됨
            
            new_match_log = ReceiptMatchLog(
                user_id=current_user.id,
                receipt_number=new_receipt_number,
                is_matched=excel_result is not None,
                excel_name=excel_result[1] if excel_result else None,
                passport_number=passport_number.strip() if passport_number.strip() else None,
                birthday=passport_info.birthday if passport_info else None,
                # 엑셀 상세 정보
                sales_date=parsed_sales_date if excel_result else None,
                category=excel_result[4] if excel_result else None,
                brand=excel_result[5] if excel_result else None,
                product_code=excel_result[6] if excel_result else None,
                discount_amount_krw=safe_float(excel_result[7]) if excel_result else None,
                sales_price_usd=safe_float(excel_result[8]) if excel_result else None,
                net_sales_krw=safe_float(excel_result[9]) if excel_result else None,
                store_branch=excel_result[10] if excel_result else None
            )
            db.add(new_match_log)
        
        # 신라 엑셀 데이터에 여권번호 업데이트 (매칭된 경우)
        if excel_result and passport_number.strip():
            try:
                update_excel_sql = text("""
                    UPDATE shilla_excel_data 
                    SET passport_number = :passport_number
                    WHERE "receiptNumber"::text = :receipt_number
                """)
                db.execute(update_excel_sql, {
                    "passport_number": passport_number.strip(),
                    "receipt_number": new_receipt_number
                })
                print(f"신라 엑셀 데이터 여권번호 업데이트: {new_receipt_number} -> {passport_number}")
            except Exception as e:
                print(f"엑셀 데이터 업데이트 오류: {e}")
        
        db.commit()
        
        print(f"신라 영수증 업데이트 완료:")
        print(f"  - 영수증번호: {old_receipt_number} -> {new_receipt_number}")
        print(f"  - 여권번호: {old_passport_number} -> {passport_number}")
        print(f"  - 엑셀 매칭: {'성공' if excel_result else '실패'}")
        
        # 매칭 성공 여부 확인
        is_matched = excel_result is not None
        
        # 다음 매칭되지 않은 신라 영수증 찾기
        next_unmatched_sql = text("""
            SELECT sr.id, sr.receipt_number, sr.file_path
            FROM shilla_receipts sr
            LEFT JOIN shilla_excel_data se ON sr.receipt_number = se."receiptNumber"::text
            WHERE sr.user_id = :user_id
            AND se."receiptNumber" IS NULL
            AND sr.id > :current_id
            ORDER BY sr.id
            LIMIT 1
        """)
        next_receipt = db.execute(next_unmatched_sql, {"user_id": current_user.id, "current_id": receipt_id}).fetchone()
        
        # JSON 응답으로 결과 반환
        return {
            "success": True,
            "matched": is_matched,
            "message": "매칭 성공" if is_matched else "매칭 실패 - 엑셀 데이터에서 해당 영수증 번호를 찾을 수 없습니다",
            "next_receipt": {
                "id": next_receipt.id,
                "receipt_number": next_receipt.receipt_number
            } if next_receipt else None,
            "has_more": next_receipt is not None
        }
        
    except Exception as e:
        db.rollback()
        print(f"영수증 업데이트 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"업데이트 중 오류가 발생했습니다: {str(e)}")
    finally:
        db.close()

@router.get("/edit_shilla_receipt/{receipt_id}")
async def edit_shilla_receipt(
    request: Request, 
    receipt_id: int,
    current_user: User = Depends(get_current_user)
):
    """신라 영수증의 여권번호 수정 페이지"""
    db = SessionLocal()
    try:
        # 신라 영수증 조회
        receipt = db.query(ShillaReceipt).filter(
            ShillaReceipt.id == receipt_id,
            ShillaReceipt.user_id == current_user.id
        ).first()
        
        if not receipt:
            raise HTTPException(status_code=404, detail="영수증을 찾을 수 없습니다.")
        
        # 해당 영수증과 매칭된 엑셀 데이터의 고객명 조회
        excel_name = None
        try:
            excel_sql = text("""
                SELECT name 
                FROM shilla_excel_data 
                WHERE "receiptNumber"::text = :receipt_number
            """)
            excel_result = db.execute(excel_sql, {"receipt_number": receipt.receipt_number}).first()
            if excel_result:
                excel_name = excel_result[0]
        except Exception as e:
            print(f"엑셀 데이터 조회 오류: {e}")
        
        # 현재 여권번호로 여권 정보 조회 (있다면)
        passport_info = None
        if receipt.passport_number:
            passport_info = db.query(Passport).filter(
                Passport.passport_number == receipt.passport_number,
                Passport.user_id == current_user.id
            ).first()
        
        # 매칭 가능한 여권 목록 조회 (매칭되지 않은 여권들)
        available_passports_sql = text("""
            SELECT DISTINCT p.name, p.passport_number, p.birthday
            FROM passports p
            WHERE p.user_id = :user_id
            AND (
                p.is_matched = FALSE 
                OR p.passport_number NOT IN (
                    SELECT DISTINCT se.passport_number 
                    FROM shilla_excel_data se 
                    WHERE se.passport_number IS NOT NULL
                )
            )
            ORDER BY p.name
        """)
        available_passports = db.execute(available_passports_sql, {"user_id": current_user.id}).fetchall()
        
        return templates.TemplateResponse(
            "edit_shilla_receipt.html",
            {
                "request": request,
                "receipt": receipt,
                "excel_name": excel_name,
                "passport_info": passport_info,
                "available_passports": available_passports,
                "user": current_user
            }
        )
    finally:
        db.close()

@router.post("/edit_shilla_receipt/{receipt_id}")
async def update_shilla_receipt(
    receipt_id: int, 
    new_passport_number: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """신라 영수증의 여권번호 업데이트"""
    db = SessionLocal()
    try:
        # 신라 영수증 조회 및 업데이트
        receipt = db.query(ShillaReceipt).filter(
            ShillaReceipt.id == receipt_id,
            ShillaReceipt.user_id == current_user.id
        ).first()
        
        if not receipt:
            raise HTTPException(status_code=404, detail="영수증을 찾을 수 없습니다.")
        
        old_passport_number = receipt.passport_number
        receipt.passport_number = new_passport_number
        
        # 새로운 여권번호로 여권 테이블에서 매칭 확인
        passport = db.query(Passport).filter(
            Passport.passport_number == new_passport_number,
            Passport.user_id == current_user.id
        ).first()
        
        if not passport:
            db.rollback()
            raise HTTPException(status_code=400, detail="입력한 여권번호와 일치하는 여권 정보가 없습니다.")
        
        # shilla_excel_data 테이블의 passport_number 업데이트
        try:
            update_excel_sql = text("""
                UPDATE shilla_excel_data 
                SET passport_number = :new_passport_number
                WHERE "receiptNumber"::text = :receipt_number
            """)
            db.execute(update_excel_sql, {
                "new_passport_number": new_passport_number,
                "receipt_number": receipt.receipt_number
            })
            print(f"신라 엑셀 데이터 여권번호 업데이트: {receipt.receipt_number} -> {new_passport_number}")
        except Exception as e:
            print(f"엑셀 데이터 업데이트 오류: {e}")
        
        # 여권의 매칭 상태 업데이트
        passport.is_matched = True
        
        # 이전 여권이 있었다면 매칭 해제
        if old_passport_number and old_passport_number != new_passport_number:
            old_passport = db.query(Passport).filter(
                Passport.passport_number == old_passport_number,
                Passport.user_id == current_user.id
            ).first()
            if old_passport:
                old_passport.is_matched = False
        
        # 매칭 로그 업데이트
        match_log = db.query(ReceiptMatchLog).filter(
            ReceiptMatchLog.receipt_number == receipt.receipt_number,
            ReceiptMatchLog.user_id == current_user.id
        ).first()
        
        if match_log:
            match_log.passport_number = new_passport_number
            match_log.birthday = passport.birthday
        
        db.commit()
        print(f"신라 영수증 여권번호 업데이트 완료: {receipt.receipt_number} -> {new_passport_number}")
        
        return RedirectResponse(
            url="/result/",
            status_code=303
        )
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"신라 영수증 업데이트 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"업데이트 중 오류가 발생했습니다: {str(e)}")
    finally:
        db.close()

@router.get("/download/receipt/session/{upload_id}")
async def download_session_receipts(
    upload_id: str,
    current_user: User = Depends(get_current_user)
):
    """세션의 모든 고객 수령증 다운로드 (ZIP 파일)"""
    try:
        receipt_service = ReceiptService()
        zip_path = receipt_service.generate_receipts_for_session(upload_id, current_user.id)
        
        if not zip_path or not os.path.exists(zip_path):
            raise HTTPException(status_code=404, detail="수령증을 생성할 수 없습니다.")
        
        # 파일 다운로드 후 임시 파일 삭제를 위한 백그라운드 태스크
        def cleanup_temp_file():
            try:
                if os.path.exists(zip_path):
                    # ZIP 파일과 임시 디렉토리 삭제
                    temp_dir = os.path.dirname(zip_path)
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    print(f"임시 파일 삭제 완료: {temp_dir}")
            except Exception as e:
                print(f"임시 파일 삭제 오류: {e}")
        
        # 파일 응답 반환
        response = FileResponse(
            path=zip_path,
            filename="수령증.zip",
            media_type="application/zip"
        )
        
        # 다운로드 후 파일 삭제 (백그라운드에서)
        import threading
        threading.Timer(10.0, cleanup_temp_file).start()  # 10초 후 삭제
        
        return response
        
    except Exception as e:
        print(f"세션 수령증 다운로드 오류: {e}")
        raise HTTPException(status_code=500, detail=f"수령증 다운로드 중 오류가 발생했습니다: {str(e)}")

@router.get("/download/receipt/customer/{upload_id}/{customer_name}")
async def download_customer_receipt(
    upload_id: str,
    customer_name: str,
    current_user: User = Depends(get_current_user)
):
    """특정 고객의 수령증 다운로드"""
    try:
        receipt_service = ReceiptService()
        receipt_path = receipt_service.generate_receipt_for_customer(upload_id, customer_name, current_user.id)
        
        if not receipt_path or not os.path.exists(receipt_path):
            raise HTTPException(status_code=404, detail="수령증을 생성할 수 없습니다.")
        
        # 파일 다운로드 후 임시 파일 삭제를 위한 백그라운드 태스크
        def cleanup_temp_file():
            try:
                temp_dir = os.path.dirname(receipt_path)
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    print(f"임시 파일 삭제 완료: {temp_dir}")
            except Exception as e:
                print(f"임시 파일 삭제 오류: {e}")
        
        # 파일 응답 반환
        response = FileResponse(
            path=receipt_path,
            filename=f"{customer_name}의 수령증.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # 다운로드 후 파일 삭제 (백그라운드에서)
        import threading
        threading.Timer(10.0, cleanup_temp_file).start()  # 10초 후 삭제
        
        return response
        
    except Exception as e:
        print(f"고객 수령증 다운로드 오류: {e}")
        raise HTTPException(status_code=500, detail=f"수령증 다운로드 중 오류가 발생했습니다: {str(e)}")

@router.get("/api/next-unmatched-receipt/")
async def get_next_unmatched_receipt(
    current_id: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """현재 영수증 다음의 매칭되지 않은 영수증을 반환"""
    try:
        # 사용자의 면세점 타입 확인
        duty_free_type = "lotte"  # 기본값
        
        # 신라 데이터가 있는지 확인
        shilla_count = db.execute(text("SELECT COUNT(*) FROM shilla_receipts WHERE user_id = :user_id"),
                                 {"user_id": current_user.id}).scalar()
        if shilla_count > 0:
            duty_free_type = "shilla"
        
        if duty_free_type == "shilla":
            # 신라 면세점: 매칭되지 않은 영수증 조회
            unmatched_sql = text("""
                SELECT sr.id, sr.receipt_number, sr.passport_number, sr.file_path
                FROM shilla_receipts sr
                LEFT JOIN shilla_excel_data se ON sr.receipt_number = se."receiptNumber"::text
                WHERE sr.user_id = :user_id
                AND se."receiptNumber" IS NULL
                AND sr.id > :current_id
                ORDER BY sr.id
                LIMIT 1
            """)
        else:
            # 롯데 면세점: 매칭되지 않은 영수증 조회
            unmatched_sql = text("""
                SELECT r.id, r.receipt_number, NULL as passport_number, r.file_path
                FROM receipts r
                JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number
                WHERE rml.is_matched = FALSE 
                AND r.user_id = :user_id 
                AND rml.user_id = :user_id
                AND r.id > :current_id
                ORDER BY r.id
                LIMIT 1
            """)
        
        result = db.execute(unmatched_sql, {"user_id": current_user.id, "current_id": current_id}).fetchone()
        
        if result:
            return {
                "next_receipt": {
                    "id": result.id,
                    "receipt_number": result.receipt_number,
                    "passport_number": result.passport_number,
                    "file_path": result.file_path,
                    "duty_free_type": duty_free_type
                },
                "has_more": True
            }
        else:
            return {"next_receipt": None, "has_more": False}
            
    except Exception as e:
        print(f"다음 매칭되지 않은 영수증 조회 오류: {str(e)}")
        return {"error": str(e)}, 500

@router.get("/api/unmatched-receipts/")
async def get_unmatched_receipts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """매칭되지 않은 영수증 전체 목록을 반환"""
    try:
        # 사용자의 면세점 타입 확인
        duty_free_type = "lotte"  # 기본값
        
        # 신라 데이터가 있는지 확인
        shilla_count = db.execute(text("SELECT COUNT(*) FROM shilla_receipts WHERE user_id = :user_id"), 
                                 {"user_id": current_user.id}).scalar()
        if shilla_count > 0:
            duty_free_type = "shilla"
        
        unmatched_receipts = []
        
        if duty_free_type == "shilla":
            # 신라 면세점: 매칭되지 않은 영수증 조회
            unmatched_sql = text("""
                SELECT sr.id, sr.receipt_number, sr.passport_number, sr.file_path
                FROM shilla_receipts sr
                LEFT JOIN shilla_excel_data se ON sr.receipt_number = se."receiptNumber"::text
                WHERE sr.user_id = :user_id
                AND se."receiptNumber" IS NULL
                ORDER BY sr.id
            """)
        else:
            # 롯데 면세점: 매칭되지 않은 영수증 조회 (receipt_number가 None인 경우도 포함)
            unmatched_sql = text("""
                SELECT r.id, r.receipt_number, NULL as passport_number, r.file_path
                FROM receipts r
                LEFT JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number AND rml.user_id = r.user_id
                WHERE r.user_id = :user_id
                AND (
                    r.receipt_number IS NULL OR
                    (rml.is_matched = FALSE AND rml.user_id = :user_id)
                )
                ORDER BY r.id
            """)
        
        results = db.execute(unmatched_sql, {"user_id": current_user.id}).fetchall()
        
        for result in results:
            unmatched_receipts.append({
                "id": result.id,
                "receipt_number": result.receipt_number,
                "passport_number": result.passport_number,
                "file_path": result.file_path
            })
        
        return {
            "receipts": unmatched_receipts,
            "duty_free_type": duty_free_type,
            "total_count": len(unmatched_receipts)
        }
            
    except Exception as e:
        print(f"매칭되지 않은 영수증 목록 조회 오류: {str(e)}")
        return {"error": str(e)}, 500