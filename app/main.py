from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Form, Depends, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, RedirectResponse
import zipfile, tempfile, os, shutil
from app.services.passportMatching import matching_passport, get_unmatched_passports, update_passport_matching_status
from app.services.testFinder2 import AiOcr
from app.services.matching import matchingResult, fetch_results
from app.services.GenerateReceiptForm import get_matched_name_and_payback
from app.core.database import SessionLocal
from app.models.models import User, Receipt, Passport, ReceiptMatchLog
from datetime import datetime
from sqlalchemy.sql import text
from sqlalchemy.orm import Session
from app.core.auth import (
    get_current_user, 
    get_current_user_optional,
    create_access_token, 
    get_db, 
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from datetime import timedelta
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(debug=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads", html=True), name="uploads")
templates = Jinja2Templates(directory="templates")


# 진행상황 전역 변수
progress = {"done":0, "total":0}


@app.get("/")
def main_page(request: Request, db: Session = Depends(get_db)):
    # 이미 로그인된 사용자는 업로드 페이지로 리다이렉트
    user = get_current_user_optional(request, db)
    if user:
        return RedirectResponse(url="/upload/", status_code=302)
    
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register") # 회원가입 페이지
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register/") # 폼 기반 회원가입
async def register_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...), 
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        # 중복 체크
        existing_user = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            if existing_user.username == username:
                return templates.TemplateResponse("register.html", {
                    "request": request,
                    "error": "이미 존재하는 사용자명입니다."
                })
            else:
                return templates.TemplateResponse("register.html", {
                    "request": request,
                    "error": "이미 존재하는 이메일입니다."
                })
        
        # 사용자 생성
        hashed_password = pwd_context.hash(password)
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return templates.TemplateResponse("register.html", {
            "request": request,
            "success": "회원가입이 완료되었습니다. 로그인해주세요."
        })
        
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": f"회원가입 중 오류가 발생했습니다: {str(e)}"
        })

@app.post("/login/")
async def login_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        user = db.query(User).filter(User.username == username).first()
        
        if not user or not pwd_context.verify(password, user.hashed_password):
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "사용자명 또는 비밀번호가 잘못되었습니다."
            })
        
        # JWT 토큰 생성
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, 
            expires_delta=access_token_expires
        )
        
        # 쿠키에 토큰 저장하고 업로드 페이지로 리다이렉트
        response = RedirectResponse(url="/upload/", status_code=302)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax"
        )
        
        return response
        
    except Exception as e:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": f"로그인 중 오류가 발생했습니다: {str(e)}"
        })

@app.get("/logout/")
async def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"message": "로그아웃 성공"}

@app.get("/upload/")
def form(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("input.html", {
        "request": request,
        "user": current_user
    })

@app.get("/progress/") # 진행상황 확인
def get_progress():
    return progress

@app.post("/result/")
async def result(
    request: Request,
    folder: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    try:
        # 시작 시간 기록
        start_time = datetime.now()
        print(f"\n처리 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        user_uploads_dir = f"uploads/user_{current_user.id}"
        os.makedirs(user_uploads_dir, exist_ok=True)
        
        # 1) ZIP 저장·해제
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, folder.filename)
        with open(path, "wb") as f: shutil.copyfileobj(folder.file, f)
        with zipfile.ZipFile(path) as z: z.extractall(tmp)

        # 2) 이미지 목록 (macOS 메타데이터 파일 제외)
        imgs = []
        for r,d,fs in os.walk(tmp):
            for f in fs:
                # macOS 메타데이터 파일과 __MACOSX 디렉토리 제외
                if (not f.startswith('._') and 
                    not r.endswith('__MACOSX') and 
                    f.lower().endswith((".jpg",".png",".jpeg"))):
                    # 이미지를 uploads 디렉토리로 복사
                    src_path = os.path.join(r, f)
                    dst_path = os.path.join("uploads", f)
                    shutil.copy2(src_path, dst_path)
                    imgs.append(dst_path)

        if not imgs:
            end_time = datetime.now()
            print(f"처리 종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"총 처리 시간: 0초")
            return templates.TemplateResponse(
                "result.html",
                {
                    "request": request,
                    "error": "ZIP 파일에 처리 가능한 이미지가 없습니다.",
                    "results": [],
                    "unmatched_receipts": [],
                    "user": current_user
                }
            )

        # 3) OCR→DB 저장
        progress["total"] = len(imgs); progress["done"]=0
        print(f"전체 이미지 수: {progress['total']}")
        for img in imgs:
            try:
                AiOcr(img, current_user.id)
            except Exception as e:
                print(f"이미지 처리 중 오류 발생: {img} - {str(e)}")
            finally:
                progress["done"] += 1
                print(f"처리 완료: {progress['done']}/{progress['total']}")

        # 4) 매칭 실행
        matchingResult(current_user.id)

        # 5) 조회용 리스트 생성
        matched, unmatched = fetch_results(current_user.id)
        
        # 6) 임시 디렉터리 삭제
        shutil.rmtree(tmp)

        # 종료 시간 기록 및 처리 시간 계산
        # ------------------------------------------------------------
        end_time = datetime.now()
        processing_time = end_time - start_time
        print(f"처리 종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"총 처리 시간: {processing_time.seconds}초 {processing_time.microseconds // 1000}밀리초")
        # ------------------------------------------------------------
        
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "results": matched,
                "unmatched_receipts": unmatched,
                "user": current_user
            }
        )
    except Exception as e:
        end_time = datetime.now()
        print(f"처리 종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"오류 발생으로 인한 처리 시간: {end_time - start_time}")
        print(f"처리 중 오류 발생: {str(e)}")
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "error": f"처리 중 오류가 발생했습니다: {str(e)}",
                "results": [],
                "unmatched_receipts": []
            }
        )

@app.get("/result/")
async def get_result(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    try:
        # 매칭된/안된 목록 조회
        matched, unmatched = fetch_results(current_user.id)
        # 여권 정보 조회
        passport_info = matching_passport(current_user.id)
        
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "results": passport_info,
                "unmatched_receipts": unmatched,
                "user": current_user
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
                "unmatched_receipts": []
            }
        )

@app.get("/generate-receipts/")
async def generate_receipts(
    request: Request, 
    current_user: User = Depends(get_current_user)
):
    try:
        # 사용자별 수령증 생성
        receipt_dir = get_matched_name_and_payback(current_user.id)
        
        # ZIP 파일로 압축
        zip_path = os.path.join(os.path.dirname(receipt_dir), "수령증_모음.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, dirs, files in os.walk(receipt_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, os.path.dirname(receipt_dir))
                    zipf.write(file_path, arcname)
        
        # 임시 파일들 정리
        shutil.rmtree(receipt_dir)
        
        # 다운로드 제공
        return FileResponse(
            path=zip_path, 
            filename="수령증_모음.zip",
            media_type="application/zip"
        )
    except Exception as e:
        print(f"수령증 생성 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"수령증 생성 중 오류가 발생했습니다: {str(e)}")

@app.get("/edit_unmatched/{receipt_id}")
async def edit_unmatched(
    request: Request, 
    receipt_id: int,
    current_user: User = Depends(get_current_user)
):
    db = SessionLocal()
    try:
        # 사용자의 영수증만 조회
        receipt = db.query(Receipt).filter(
            Receipt.id == receipt_id,
            Receipt.user_id == current_user.id
        ).first()
        if not receipt:
            raise HTTPException(status_code=404, detail="영수증을 찾을 수 없습니다.")
        
        return templates.TemplateResponse(
            "edit_unmatched.html",
            {
                "request": request,
                "receipt": receipt,
                "user": current_user
            }
        )
    finally:
        db.close()

@app.post("/edit_unmatched/{receipt_id}")
async def update_unmatched(
    receipt_id: int, 
    new_receipt_number: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    db = SessionLocal()
    try:
        # 사용자의 영수증만 조회 및 업데이트
        receipt = db.query(Receipt).filter(
            Receipt.id == receipt_id,
            Receipt.user_id == current_user.id
        ).first()
        if not receipt:
            raise HTTPException(status_code=404, detail="영수증을 찾을 수 없습니다.")
        
        old_receipt_number = receipt.receipt_number
        receipt.receipt_number = new_receipt_number
        
        # excel_data에서 새 영수증 번호로 검색
        sql = text("""
            SELECT "receiptNumber"
            FROM excel_data
            WHERE "receiptNumber" = :receipt_number
        """)
        result = db.execute(sql, {"receipt_number": new_receipt_number}).first()
        
        # 사용자의 매칭 로그 업데이트
        match_log = db.query(ReceiptMatchLog).filter(
            ReceiptMatchLog.receipt_number == old_receipt_number,
            ReceiptMatchLog.user_id == current_user.id
        ).first()
        
        if match_log:
            match_log.receipt_number = new_receipt_number
            if result:
                match_log.is_matched = True
            else:
                match_log.is_matched = False
        
        db.commit()
        
        return RedirectResponse(
            url="/result/",
            status_code=303
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
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
            # 여권 정보 조회 - 조건을 단순화
            sql = text("""
                SELECT p.name as passport_name, p.passport_number, p.birthday, p.file_path
                FROM passports p
                WHERE p.name = :name AND p.user_id = :user_id
            """)
            result = db.execute(sql, {"name": name, "user_id": current_user.id}).first()
            
            # 만약 정확한 이름으로 찾지 못했다면, 유사한 이름으로 검색
            if not result:
                sql = text("""
                    SELECT p.name as passport_name, p.passport_number, p.birthday, p.file_path
                    FROM passports p
                    WHERE p.user_id = :user_id
                    ORDER BY p.id DESC
                    LIMIT 1
                """)
                result = db.execute(sql, {"user_id": current_user.id}).first()
            
            if not result:
                # 여권 정보가 없는 경우 기본값으로 새 객체 생성
                passport = Passport(
                    name=name,
                    passport_number="",
                    birthday=None,
                    file_path=""
                )
                print(f"여권 정보를 찾을 수 없음. 기본값으로 생성: {name}")
            else:
                # Passport 객체 생성
                passport = Passport(
                    name=result[0],  # passport_name
                    passport_number=result[1],  # passport_number
                    birthday=result[2],  # birthday
                    file_path=result[3]  # file_path
                )
                print(f"여권 정보 찾음: {passport.name}")
            
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
            # 오류 발생 시에도 기본값으로 처리
            passport = Passport(
                name=name,
                passport_number="",
                birthday=None,
                file_path=""
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
            
            # excel_data에서 새 이름으로 검색
            sql = text("""
                SELECT "receiptNumber", name, "PayBack" 
                FROM excel_data 
                WHERE name = :name
            """)
            excel_result = db.execute(sql, {"name": new_name}).first()
            
            # 매칭 로그 업데이트
            if excel_result:
                # 매칭된 경우 receipt_match_log 업데이트
                match_log = db.query(ReceiptMatchLog).filter(
                    ReceiptMatchLog.receipt_number == excel_result[0],
                    ReceiptMatchLog.user_id == current_user.id
                ).first()
                
                if match_log:
                    match_log.is_matched = True
                    match_log.excel_name = excel_result[1]
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