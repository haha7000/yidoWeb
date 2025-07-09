from fastapi import APIRouter, Request, HTTPException, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, RedirectResponse
from app.services.passportMatching import matching_passport, get_unmatched_passports, get_matched_passports
from app.core.database import SessionLocal
from app.models.models import User, Receipt, Passport, ReceiptMatchLog, ShillaReceipt
from datetime import datetime
from sqlalchemy.sql import text
from sqlalchemy.orm import Session
from app.core.auth import get_current_user, get_db
from app.core.config import settings

router = APIRouter()
templates = Jinja2Templates(directory=settings.templates_dir)

@router.get("/edit_passport/{name}")
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

@router.get("/edit_passport_by_id/{passport_id}")
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

@router.post("/update_passport_by_id/{passport_id}")
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

@router.post("/update_passport/{name}")
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

@router.get("/unmatched-passports/")
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

@router.get("/matched-passports/")
async def matched_passports_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """매칭된 여권 관리 페이지"""
    try:
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