from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Form, Depends, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
import zipfile, tempfile, os, shutil
from app.services.passportMatching import matching_passport, get_unmatched_passports, update_passport_matching_status, get_matched_passports
from app.services.LotteFinder import LotteAiOcr
from app.services.ShillaFinder import ShillaAiOcr
from app.services.matching import matchingResult, fetch_results
from app.services.shilla_matching import shilla_matching_result
from app.utils.helpers import safe_float
from app.core.database import SessionLocal
from app.models.models import User, Receipt, Passport, ReceiptMatchLog, DutyFreeType, ShillaReceipt, ProcessingHistory, UnrecognizedImage
from app.services.data_manager import DataManager
from app.services.archive_service import ArchiveService
from app.services.receipt_service import ReceiptService
from datetime import datetime
from sqlalchemy.sql import text
from sqlalchemy.orm import Session
from app.core.auth import get_current_user, get_current_user_optional, create_access_token, get_db, ACCESS_TOKEN_EXPIRE_MINUTES
from datetime import timedelta
from passlib.context import CryptContext
import pandas as pd
import time
import uuid
from fastapi.responses import FileResponse
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") # 비밀번호 해싱


app = FastAPI(debug=True)
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
app.mount("/uploads", StaticFiles(directory=settings.uploads_dir, html=True), name="uploads")
templates = Jinja2Templates(directory=settings.templates_dir)

# 라우터 등록
from app.routers import auth, api, upload
from app.routers.upload import calculate_fully_matched_customers, calculate_passport_statistics
app.include_router(auth.router, tags=["인증"])
app.include_router(api.router, tags=["API"])
app.include_router(upload.router, tags=["업로드"])

@app.get("/result/")
async def get_result(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # 사용자의 마지막 처리 타입을 확인
        duty_free_type = "lotte"  # 기본값
        
        # 먼저 신라 데이터가 있는지 확인
        try:
            shilla_count_sql = text("""
                SELECT COUNT(*) FROM shilla_receipts 
                WHERE user_id = :user_id
            """)
            shilla_count = db.execute(shilla_count_sql, {"user_id": current_user.id}).scalar()
            
            if shilla_count > 0:
                duty_free_type = "shilla"
                print(f"신라 영수증 {shilla_count}개 발견, 신라 모드로 설정")
            else:
                # 롯데 데이터 확인
                lotte_count_sql = text("""
                    SELECT COUNT(*) FROM receipts 
                    WHERE user_id = :user_id
                """)
                lotte_count = db.execute(lotte_count_sql, {"user_id": current_user.id}).scalar()
                
                if lotte_count > 0:
                    duty_free_type = "lotte"
                    print(f"롯데 영수증 {lotte_count}개 발견, 롯데 모드로 설정")
                
        except Exception as e:
            print(f"테이블 조회 오류: {e}")
            # 테이블이 없는 경우 기본값 유지
        
        print(f"결과 조회 - 사용자: {current_user.id}, 면세점 타입: {duty_free_type}")
        
        # 매칭된/안된 목록 조회
        matched, unmatched = fetch_results(current_user.id, duty_free_type)
        # 여권 정보 조회
        passport_info = matching_passport(current_user.id, duty_free_type)
        
        # 영수증과 여권이 모두 매칭된 고객 수 계산
        fully_matched_customers = calculate_fully_matched_customers(current_user.id, duty_free_type, db)
        
        # 여권 통계 계산
        passport_stats = calculate_passport_statistics(current_user.id, duty_free_type, db)
        
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "results": passport_info,
                "unmatched_receipts": unmatched,
                "fully_matched_customers": fully_matched_customers,
                "passport_stats": passport_stats,
                "user": current_user,
                "duty_free_type": duty_free_type
            }
        )
    except Exception as e:
        print(f"결과 조회 중 오류 발생: {str(e)}")
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "error": f"결과 조회 중 오류가 발생했습니다: {str(e)}",
                "results": [],
                "unmatched_receipts": [],
                "fully_matched_customers": 0,
                "passport_stats": {"total_passports": 0, "matched_passports": 0, "unmatched_passports": 0},
                "user": current_user,
                "duty_free_type": "lotte"
            }
        )

@app.get("/generate-receipts/")
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

@app.get("/edit_unmatched/{receipt_id}")
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

@app.post("/edit_unmatched/{receipt_id}")
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

@app.get("/edit_passport/{name}")
async def edit_passport(
    request: Request,
    name: str,
    current_user: User = Depends(get_current_user)
    ):
    with SessionLocal() as db:
        try:
            # 실제 데이터베이스에서 여권 객체 조회
            passport = db.query(Passport).filter(
                Passport.name == name,
                Passport.user_id == current_user.id
            ).first()
            
            # 만약 정확한 이름으로 찾지 못했다면, 유사한 이름으로 검색
            if not passport:
                passport = db.query(Passport).filter(
                    Passport.user_id == current_user.id
                ).order_by(Passport.id.desc()).first()
            
            if not passport:
                # 여권 정보가 없는 경우 새로 생성하고 저장
                passport = Passport(
                    user_id=current_user.id,
                    name=name,
                    passport_number="",
                    birthday=None,
                    file_path="",
                    is_matched=False
                )
                db.add(passport)
                db.commit()
                db.refresh(passport)  # ID를 포함한 전체 정보 새로고침
                print(f"여권 정보를 찾을 수 없어서 새로 생성: {name}, ID: {passport.id}")
            else:
                print(f"여권 정보 찾음: {passport.name}, ID: {passport.id}")
            
            return templates.TemplateResponse(
                "edit_passport.html",
                {
                    "request": request,
                    "passport": passport,
                    "name": name,
                    "user": current_user
                }
            )
        except Exception as e:
            print(f"edit_passport 오류: {str(e)}")
            # 오류 발생 시에도 기본값으로 처리하되, 실제 DB에 저장
            try:
                passport = Passport(
                    user_id=current_user.id,
                    name=name,
                    passport_number="",
                    birthday=None,
                    file_path="",
                    is_matched=False
                )
                db.add(passport)
                db.commit()
                db.refresh(passport)
            except:
                # DB 저장도 실패한 경우 임시 객체 생성
                passport = Passport(
                    id=0,  # 임시 ID
                    user_id=current_user.id,
                    name=name,
                    passport_number="",
                    birthday=None,
                    file_path="",
                    is_matched=False
                )
            
            return templates.TemplateResponse(
                "edit_passport.html",
                {
                    "request": request,
                    "passport": passport,
                    "name": name,
                    "user": current_user,
                    "error": f"여권 정보를 불러오는 중 오류가 발생했습니다: {str(e)}"
                }
            )

@app.get("/edit_passport_by_id/{passport_id}")
async def edit_passport_by_id(
    request: Request,
    passport_id: int,
    current_user: User = Depends(get_current_user)
    ):
    with SessionLocal() as db:
        try:
            # ID로 직접 여권 객체 조회
            passport = db.query(Passport).filter(
                Passport.id == passport_id,
                Passport.user_id == current_user.id
            ).first()
            
            if not passport:
                raise HTTPException(status_code=404, detail="여권 정보를 찾을 수 없습니다.")
            
            print(f"ID로 여권 정보 찾음: {passport.name}, ID: {passport.id}")
            
            return templates.TemplateResponse(
                "edit_passport.html",
                {
                    "request": request,
                    "passport": passport,
                    "name": passport.name or "unknown",
                    "user": current_user
                }
            )
        except HTTPException:
            raise
        except Exception as e:
            print(f"edit_passport_by_id 오류: {str(e)}")
            raise HTTPException(status_code=500, detail=f"여권 정보를 불러오는 중 오류가 발생했습니다: {str(e)}")

@app.post("/update_passport_by_id/{passport_id}")
async def update_passport_by_id(
    request: Request,
    passport_id: int,
    new_name: str = Form(...),
    passport_number: str = Form(None),
    birthday: str = Form(None),
    current_user: User = Depends(get_current_user)
):
    with SessionLocal() as db:
        try:
            # ID로 기존 여권 정보 조회
            passport = db.query(Passport).filter(
                Passport.id == passport_id,
                Passport.user_id == current_user.id
            ).first()
            
            if not passport:
                raise HTTPException(status_code=404, detail="여권 정보를 찾을 수 없습니다.")
            
            old_name = passport.name
            
            # 여권 정보 업데이트
            passport.name = new_name
            if passport_number:
                passport.passport_number = passport_number
            if birthday:
                try:
                    passport.birthday = datetime.strptime(birthday, '%Y-%m-%d').date()
                except ValueError:
                    print(f"잘못된 날짜 형식: {birthday}")
            
            # 모든 면세점 타입에서 검색 (동적 테이블 조회)
            excel_result = None
            try:
                # 롯데 데이터에서 검색
                lotte_sql = text("""
                    SELECT "receiptNumber", name, "PayBack" 
                    FROM lotte_excel_data 
                    WHERE name = :name
                """)
                excel_result = db.execute(lotte_sql, {"name": new_name}).first()
                
                if not excel_result:
                    # 신라 데이터에서 검색 (여권번호로 매칭)
                    if passport_number:  # 여권번호가 있는 경우에만
                        shilla_sql = text("""
                            SELECT "receiptNumber", name, "PayBack" 
                            FROM shilla_excel_data 
                            WHERE passport_number = :passport_number
                        """)
                        excel_result = db.execute(shilla_sql, {"passport_number": passport_number}).first()
                        print(f"신라 데이터 여권번호 매칭 시도: {passport_number}")
                    else:
                        print("신라 데이터 매칭을 위해서는 여권번호가 필요합니다.")
            except Exception as e:
                print(f"엑셀 데이터 검색 오류: {e}")
                
            # 매칭 로그 업데이트
            if excel_result:
                # 매칭된 경우 receipt_match_log 업데이트
                match_log = db.query(ReceiptMatchLog).filter(
                    ReceiptMatchLog.receipt_number == excel_result[0],
                    ReceiptMatchLog.user_id == current_user.id
                ).first()
                
                if match_log:
                    match_log.is_matched = True
                    match_log.excel_name = new_name  # 여권 풀네임으로 업데이트
                    match_log.passport_number = passport_number
                    match_log.birthday = passport.birthday
                
                # 여권 매칭 상태 업데이트
                passport.is_matched = True
                print(f"여권 매칭 성공: {new_name} -> {excel_result[0]}")
            else:
                # 매칭되지 않은 경우
                passport.is_matched = False
                print(f"여권 매칭 실패: {new_name}")
            
            db.commit()
            print(f"여권 정보 업데이트 완료: {old_name} (ID: {passport_id}) -> {new_name}")
            
            # 매칭 성공 여부 확인
            is_matched = excel_result is not None
            
            # 다음 매칭되지 않은 여권 찾기 (ID 기반)
            unmatched_passports = get_unmatched_passports(current_user.id)
            
            # 현재 여권의 다음 여권 찾기 (ID 기반으로 비교)
            next_passport = None
            current_found = False
            for passport_item in unmatched_passports:
                if current_found:
                    next_passport = passport_item
                    break
                if passport_item.get('id') == passport_id:
                    current_found = True
            
            # JSON 응답으로 결과 반환
            return {
                "success": True,
                "matched": is_matched,
                "message": "매칭 완료" if is_matched else "매칭 실패 - 엑셀 데이터에서 해당 이름을 찾을 수 없습니다",
                "next_passport": {
                    "id": next_passport['id'],
                    "name": next_passport['passport_name']
                } if next_passport else None,
                "has_more": next_passport is not None
            }
            
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            print(f"update_passport_by_id 오류: {str(e)}")
            raise HTTPException(status_code=500, detail=f"업데이트 중 오류가 발생했습니다: {str(e)}")

@app.post("/update_passport/{name}")
async def update_passport(
    request: Request,
    name: str,
    new_name: str = Form(...),
    passport_number: str = Form(None),
    birthday: str = Form(None),
    current_user: User = Depends(get_current_user)
):
    with SessionLocal() as db:
        try:
            # 기존 여권 정보 조회
            passport = db.query(Passport).filter(
                Passport.name == name,
                Passport.user_id == current_user.id
            ).first()
            
            # 여권 정보가 없으면 새로 생성
            if not passport:
                print(f"여권 정보가 없어서 새로 생성: {name}")
                passport = Passport(
                    user_id=current_user.id,
                    name=name,
                    passport_number="",
                    birthday=None,
                    file_path=""
                )
                db.add(passport)
                db.flush()  # ID 생성을 위해 flush
            
            # 여권 정보 업데이트
            passport.name = new_name
            if passport_number:
                passport.passport_number = passport_number
            if birthday:
                try:
                    passport.birthday = datetime.strptime(birthday, '%Y-%m-%d').date()
                except ValueError:
                    print(f"잘못된 날짜 형식: {birthday}")
            
            # 모든 면세점 타입에서 검색 (동적 테이블 조회)
            excel_result = None
            try:
                # 롯데 데이터에서 검색
                lotte_sql = text("""
                    SELECT "receiptNumber", name, "PayBack" 
                    FROM lotte_excel_data 
                    WHERE name = :name
                """)
                excel_result = db.execute(lotte_sql, {"name": new_name}).first()
                
                if not excel_result:
                    # 신라 데이터에서 검색 (여권번호로 매칭)
                    if passport_number:  # 여권번호가 있는 경우에만
                        shilla_sql = text("""
                            SELECT "receiptNumber", name, "PayBack" 
                            FROM shilla_excel_data 
                            WHERE passport_number = :passport_number
                        """)
                        excel_result = db.execute(shilla_sql, {"passport_number": passport_number}).first()
                        print(f"신라 데이터 여권번호 매칭 시도: {passport_number}")
                    else:
                        print("신라 데이터 매칭을 위해서는 여권번호가 필요합니다.")
            except Exception as e:
                print(f"엑셀 데이터 검색 오류: {e}")
                
            # 매칭 로그 업데이트
            if excel_result:
                # 매칭된 경우 receipt_match_log 업데이트
                match_log = db.query(ReceiptMatchLog).filter(
                    ReceiptMatchLog.receipt_number == excel_result[0],
                    ReceiptMatchLog.user_id == current_user.id
                ).first()
                
                if match_log:
                    match_log.is_matched = True
                    match_log.excel_name = new_name  # 여권 풀네임으로 업데이트
                    match_log.passport_number = passport_number
                    match_log.birthday = passport.birthday
                
                # 여권 매칭 상태 업데이트
                passport.is_matched = True
                print(f"여권 매칭 성공: {new_name} -> {excel_result[0]}")
            else:
                # 매칭되지 않은 경우
                passport.is_matched = False
                print(f"여권 매칭 실패: {new_name}")
            
            db.commit()
            print(f"여권 정보 업데이트 완료: {name} -> {new_name}")
            
            # 다음 매칭되지 않은 여권 찾기
            unmatched_passports = get_unmatched_passports(current_user.id)
            
            # 현재 여권의 다음 여권 찾기
            next_passport = None
            current_found = False
            for passport_item in unmatched_passports:
                if current_found:
                    next_passport = passport_item
                    break
                # passport_item은 딕셔너리이므로 키로 접근
                passport_name = passport_item.get('passport_name') if isinstance(passport_item, dict) else passport_item.name
                if passport_name == name:
                    current_found = True
            
            # 다음 여권이 있으면 해당 여권 편집 페이지로, 없으면 목록 페이지로
            if next_passport:
                # next_passport도 딕셔너리 형태
                next_name = next_passport.get('passport_name') if isinstance(next_passport, dict) else next_passport.name
                return RedirectResponse(
                    url=f"/edit_passport/{next_name}",
                    status_code=303
                )
            else:
                return RedirectResponse(
                    url="/unmatched-passports/",
                    status_code=303
                )
            
        except Exception as e:
            db.rollback()
            print(f"update_passport 오류: {str(e)}")
            return templates.TemplateResponse(
                "edit_passport.html",
                {
                    "request": request,
                    "passport": Passport(name=name, passport_number="", birthday=None, file_path=""),
                    "name": name,
                    "user": current_user,
                    "error": f"여권 정보 업데이트 중 오류가 발생했습니다: {str(e)}"
                }
            )

@app.get("/unmatched-passports/")
async def unmatched_passports(
    request: Request,
    current_user: User = Depends(get_current_user)
    ):
    try:
        unmatched_passports = get_unmatched_passports(current_user.id)
        return templates.TemplateResponse(
            "unmatched_passports.html",
            {
                "request": request,
                "unmatched_passports": unmatched_passports,
                "user": current_user
            }
        )
    except Exception as e:
        print(f"매칭안된 여권 목록 조회 중 오류 발생: {str(e)}")
        return templates.TemplateResponse(
            "unmatched_passports.html",
            {
                "request": request,
                "error": f"매칭안된 여권 목록 조회 중 오류가 발생했습니다: {str(e)}",
                "unmatched_passports": [],
                "user": current_user
            }
        )
    
@app.get("/edit_shilla_receipt/{receipt_id}")
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

@app.post("/edit_shilla_receipt/{receipt_id}")
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

@app.post("/complete-session/")
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
        
        # receipt_match_log 테이블 초기화
        deleted_count = db.query(ReceiptMatchLog).filter(
            ReceiptMatchLog.user_id == current_user.id
        ).delete()
        print(f"receipt_match_log {deleted_count}개 삭제")
        
        # 다른 테이블들도 초기화
        receipt_deleted = db.query(Receipt).filter(Receipt.user_id == current_user.id).delete()
        shilla_deleted = db.query(ShillaReceipt).filter(ShillaReceipt.user_id == current_user.id).delete()
        passport_deleted = db.query(Passport).filter(Passport.user_id == current_user.id).delete()
        
        print(f"기타 테이블 삭제: receipts={receipt_deleted}, shilla_receipts={shilla_deleted}, passports={passport_deleted}")
        
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

@app.get("/history/")
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

@app.get("/history/search/")
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

@app.get("/history/session-detail/{upload_id}")
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

@app.delete("/history/delete-session/{upload_id}")
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
    

@app.get("/fee/", response_class=HTMLResponse)
async def fee_management_page(request: Request, current_user: User = Depends(get_current_user)):
    """수수료 적용기준 관리 페이지"""
    return templates.TemplateResponse("fee.html", {
        "request": request,
        "user": current_user
    })

# ============ 수수료 관련 API들은 app/routers/api.py로 이동됨 ============

# ============ 수령증 다운로드 API ============

@app.get("/download/receipt/session/{upload_id}")
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

@app.get("/download/receipt/customer/{upload_id}/{customer_name}")
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

# ============ 여권/영수증 관련 API들은 app/routers/api.py로 이동됨 ============

# ============ 모든 API 엔드포인트들은 app/routers/api.py로 이동됨 ============

@app.get("/api/next-unmatched-receipt/")
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

@app.get("/api/unmatched-receipts/")
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

@app.post("/api/change-type/")
async def change_item_type(
    item_id: int = Form(...),
    current_type: str = Form(...),  # "receipt", "passport", "unrecognized"
    new_type: str = Form(...),  # "receipt", "passport", "delete"
    passport_name: str = Form(None),  # 여권의 경우 이름도 함께 전달
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """항목의 유형을 변경합니다 (영수증 ↔ 여권 ↔ 삭제)"""
    try:
        # 현재 항목 조회
        current_item = None
        if current_type == "receipt":
            # 롯데 영수증 확인
            current_item = db.query(Receipt).filter(
                Receipt.id == item_id,
                Receipt.user_id == current_user.id
            ).first()
            
            # 신라 영수증 확인
            if not current_item:
                current_item = db.query(ShillaReceipt).filter(
                    ShillaReceipt.id == item_id,
                    ShillaReceipt.user_id == current_user.id
                ).first()
                current_type = "shilla_receipt"
                
        elif current_type == "passport":
            # 먼저 ID로 검색
            current_item = db.query(Passport).filter(
                Passport.id == item_id,
                Passport.user_id == current_user.id
            ).first()
            
            # ID로 찾지 못했다면 이름으로 검색
            if not current_item and passport_name:
                current_item = db.query(Passport).filter(
                    Passport.name == passport_name,
                    Passport.user_id == current_user.id
                ).first()
            
        elif current_type == "unrecognized":
            current_item = db.query(UnrecognizedImage).filter(
                UnrecognizedImage.id == item_id,
                UnrecognizedImage.user_id == current_user.id
            ).first()
        
        if not current_item:
            return JSONResponse(content={"success": False, "message": "항목을 찾을 수 없습니다."}, status_code=404)
        
        file_path = current_item.file_path
        upload_id = getattr(current_item, 'upload_id', None)
        
        # 삭제 처리
        if new_type == "delete":
            db.delete(current_item)
            
            # 관련 매칭 로그도 삭제 (영수증인 경우)
            if current_type in ["receipt", "shilla_receipt"]:
                if hasattr(current_item, 'receipt_number') and current_item.receipt_number:
                    db.query(ReceiptMatchLog).filter(
                        ReceiptMatchLog.receipt_number == current_item.receipt_number,
                        ReceiptMatchLog.user_id == current_user.id
                    ).delete()
            
            db.commit()
            return JSONResponse(content={"success": True, "message": "항목이 삭제되었습니다."})
        
        # 타입 변경 처리
        if new_type == "receipt":
            # 면세점 타입 확인
            duty_free_type = "lotte"  # 기본값
            shilla_count = db.execute(text("SELECT COUNT(*) FROM shilla_receipts WHERE user_id = :user_id"), 
                                     {"user_id": current_user.id}).scalar()
            if shilla_count > 0:
                duty_free_type = "shilla"
            
            if duty_free_type == "shilla":
                new_item = ShillaReceipt(
                    user_id=current_user.id,
                    upload_id=upload_id,
                    file_path=file_path,
                    receipt_number=None,
                    passport_number=None
                )
            else:
                new_item = Receipt(
                    user_id=current_user.id,
                    upload_id=upload_id,
                    file_path=file_path,
                    receipt_number=None
                )
            
            db.add(new_item)
            
            # 롯데 면세점의 경우, receipt_number가 None인 영수증은 자동으로 매칭되지 않은 것으로 처리됨
            # (매칭 로그는 영수증 번호가 입력될 때 생성됨)
            
        elif new_type == "passport":
            new_item = Passport(
                user_id=current_user.id,
                upload_id=upload_id,
                file_path=file_path,
                passport_number=None,
                birthday=None,
                name=None,
                is_matched=False
            )
            db.add(new_item)
            
        elif new_type == "unrecognized":
            new_item = UnrecognizedImage(
                user_id=current_user.id,
                upload_id=upload_id,
                file_path=file_path
            )
            db.add(new_item)
        
        # 기존 항목 삭제
        db.delete(current_item)
        
        # 관련 매칭 로그 정리 (영수증인 경우)
        if current_type in ["receipt", "shilla_receipt"]:
            if hasattr(current_item, 'receipt_number') and current_item.receipt_number:
                db.query(ReceiptMatchLog).filter(
                    ReceiptMatchLog.receipt_number == current_item.receipt_number,
                    ReceiptMatchLog.user_id == current_user.id
                ).delete()
        
        db.commit()
        
        type_names = {
            "receipt": "영수증",
            "passport": "여권", 
            "unrecognized": "인식안된 이미지"
        }
        
        return JSONResponse(content={
            "success": True, 
            "message": f"항목이 {type_names.get(new_type, new_type)}(으)로 변경되었습니다.",
            "new_id": new_item.id if new_type != "delete" else None
        })
        
    except Exception as e:
        db.rollback()
        print(f"유형 변경 오류: {str(e)}")
        return JSONResponse(content={"success": False, "message": f"유형 변경 중 오류가 발생했습니다: {str(e)}"}, status_code=500)

@app.get("/api/unrecognized-images/")
async def get_unrecognized_images(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """인식되지 않은 이미지 목록을 반환"""
    try:
        unrecognized_images = db.query(UnrecognizedImage).filter(
            UnrecognizedImage.user_id == current_user.id
        ).order_by(UnrecognizedImage.created_at.desc()).all()
        
        images = []
        for img in unrecognized_images:
            images.append({
                "id": img.id,
                "file_path": img.file_path,
                "created_at": img.created_at.isoformat() if img.created_at else None
            })
        
        return {
            "images": images,
            "total_count": len(images)
        }
        
    except Exception as e:
        print(f"인식되지 않은 이미지 조회 오류: {str(e)}")
        return {"error": str(e)}

@app.post("/api/delete-all-unrecognized/")
async def delete_all_unrecognized_images(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """모든 인식되지 않은 이미지를 삭제합니다"""
    try:
        # 현재 사용자의 인식되지 않은 이미지 조회
        unrecognized_images = db.query(UnrecognizedImage).filter(
            UnrecognizedImage.user_id == current_user.id
        ).all()
        
        deleted_count = len(unrecognized_images)
        
        if deleted_count == 0:
            return {"success": True, "deleted_count": 0, "message": "삭제할 이미지가 없습니다."}
        
        # 모든 이미지 삭제
        db.query(UnrecognizedImage).filter(
            UnrecognizedImage.user_id == current_user.id
        ).delete()
        
        db.commit()
        
        return {
            "success": True, 
            "deleted_count": deleted_count,
            "message": f"{deleted_count}개의 인식되지 않은 이미지가 삭제되었습니다."
        }
        
    except Exception as e:
        db.rollback()
        print(f"전체 삭제 오류: {str(e)}")
        return {"success": False, "message": f"전체 삭제 중 오류가 발생했습니다: {str(e)}"}

@app.get("/unrecognized-images/")
async def unrecognized_images_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """인식되지 않은 이미지 관리 페이지"""
    return templates.TemplateResponse(
        "unrecognized_images.html",
        {
            "request": request,
            "user": current_user
        }
    )

@app.post("/api/update-customer-names/")
async def update_customer_names_to_passport_names(
    current_user: User = Depends(get_current_user)
):
    """기존 저장된 데이터의 고객명을 여권 풀네임으로 업데이트"""
    try:
        receipt_service = ReceiptService()
        result = receipt_service.update_excel_names_to_passport_names(current_user.id)
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "details": {
                    "updated_receipt_logs": result["updated_receipt_logs"],
                    "updated_history": result["updated_history"]
                }
            }
        else:
            return {
                "success": False,
                "error": result["error"]
            }
            
    except Exception as e:
        print(f"고객명 업데이트 API 오류: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/matched-passports/")
async def matched_passports_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """매칭된 여권 관리 페이지"""
    try:
        from app.services.passportMatching import get_matched_passports
        
        # 매칭된 여권 목록 조회
        matched_passports = get_matched_passports(current_user.id)
        
        return templates.TemplateResponse(
            "matched_passports.html",
            {
                "request": request,
                "matched_passports": matched_passports,
                "user": current_user
            }
        )
        
    except Exception as e:
        print(f"매칭된 여권 페이지 로드 오류: {str(e)}")
        return templates.TemplateResponse(
            "matched_passports.html",
            {
                "request": request,
                "error": f"매칭된 여권 조회 중 오류가 발생했습니다: {str(e)}",
                "matched_passports": [],
                "user": current_user
            }
        )