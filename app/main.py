from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, RedirectResponse
import zipfile, tempfile, os, shutil
from app.services.passportMatching import matching_passport, get_unmatched_passports, update_passport_matching_status
from app.services.testFinder2 import AiOcr
from app.services.matching import matchingResult, fetch_results
from app.services.GenerateReceiptForm import get_matched_name_and_payback
from app.core.database import SessionLocal
from app.models.models import Receipt, Passport, ReceiptMatchLog
from datetime import datetime
from sqlalchemy.sql import text
# fetch_results(): 매칭된/안된 목록 리턴 함수
# GenerateReceiptForm.get_matched_name_and_payback() 는 필요 시 호출

app = FastAPI(debug=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads", html=True), name="uploads")
templates = Jinja2Templates(directory="templates")

ExcelPath = "/Users/gimdonghun/Downloads/test12.xlsx"

# 진행상황 전역 변수
progress = {"done":0, "total":0}

@app.get("/")
def form(request: Request):
    return templates.TemplateResponse("input.html", {"request": request})

@app.get("/progress/") # 진행상황 확인
def get_progress():
    return progress

@app.post("/result/")
async def result(request: Request, folder: UploadFile = File(...)):
    try:
        # 시작 시간 기록
        start_time = datetime.now()
        print(f"\n처리 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
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
                    "unmatched_receipts": []
                }
            )

        # 3) OCR→DB 저장
        progress["total"] = len(imgs); progress["done"]=0
        print(f"전체 이미지 수: {progress['total']}")
        for img in imgs:
            try:
                AiOcr(img)
            except Exception as e:
                print(f"이미지 처리 중 오류 발생: {img} - {str(e)}")
            finally:
                progress["done"] += 1
                print(f"처리 완료: {progress['done']}/{progress['total']}")

        # 4) 매칭 실행
        matchingResult()

        # 5) 조회용 리스트 생성
        matched, unmatched = fetch_results()
        
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
                "unmatched_receipts": unmatched
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
async def get_result(request: Request):
    try:
        # 매칭된/안된 목록 조회
        matched, unmatched = fetch_results()
        # 여권 정보 조회
        passport_info = matching_passport()
        
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "results": passport_info,
                "unmatched_receipts": unmatched
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
async def generate_receipts(request: Request):
    try:
        # 수령증 생성
        receipt_dir = get_matched_name_and_payback()
        
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
async def edit_unmatched(request: Request, receipt_id: int):
    db = SessionLocal()
    try:
        # 영수증 정보 조회
        receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
        if not receipt:
            raise HTTPException(status_code=404, detail="영수증을 찾을 수 없습니다.")
        
        return templates.TemplateResponse(
            "edit_unmatched.html",
            {
                "request": request,
                "receipt": receipt
            }
        )
    finally:
        db.close()

@app.post("/edit_unmatched/{receipt_id}")
async def update_unmatched(receipt_id: int, new_receipt_number: str = Form(...)):
    db = SessionLocal()
    try:
        # 영수증 정보 조회 및 업데이트
        receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
        if not receipt:
            raise HTTPException(status_code=404, detail="영수증을 찾을 수 없습니다.")
        
        old_receipt_number = receipt.receipt_number  # 기존 영수증 번호 저장
        receipt.receipt_number = new_receipt_number  # 새 영수증 번호로 업데이트
        
        # excel_data에서 새 영수증 번호로 검색
        sql = text("""
            SELECT "receiptNumber"
            FROM excel_data
            WHERE "receiptNumber" = :receipt_number
        """)
        result = db.execute(sql, {"receipt_number": new_receipt_number}).first()
        
        # 매칭 로그 업데이트 (기존 영수증 번호로 찾기)
        match_log = db.query(ReceiptMatchLog).filter(
            ReceiptMatchLog.receipt_number == old_receipt_number
        ).first()
        
        if match_log:
            match_log.receipt_number = new_receipt_number  # 영수증 번호 업데이트
            if result:  # excel_data에 매칭되는 데이터가 있으면
                match_log.is_matched = True
            else:  # 매칭되는 데이터가 없으면
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
async def edit_passport(request: Request, name: str):
    with SessionLocal() as db:
        try:
            # 여권 정보 조회 (raw SQL 사용)
            sql = text("""
                SELECT p.name as passport_name, p.passport_number, p.birthday, p.file_path
                FROM passports p
                LEFT JOIN excel_data e ON p.name = e."name"
                WHERE (p.name = :name OR p.name IS NULL)
                AND e."name" IS NULL
            """)
            result = db.execute(sql, {"name": name}).first()
            
            if not result:
                raise HTTPException(status_code=404, detail="여권 정보를 찾을 수 없습니다.")
            
            # Passport 객체 생성
            passport = Passport(
                name=result[0],  # passport_name
                passport_number=result[1],  # passport_number
                birthday=result[2],  # birthday
                file_path=result[3]  # file_path
            )
            
            return templates.TemplateResponse(
                "edit_passport.html",
                {
                    "request": request,
                    "passport": passport,
                    "name": name
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/update_passport/{name}")
async def update_passport(
    request: Request,
    name: str,
    new_name: str = Form(...),
    passport_number: str = Form(None),
    birthday: str = Form(None)
):
    with SessionLocal() as db:
        try:
            # 여권 정보 업데이트
            sql = text("""
                SELECT p.id, p.name, p.passport_number, p.birthday, p.file_path
                FROM passports p
                LEFT JOIN excel_data e ON p.name = e."name"
                WHERE (p.name = :name OR p.name IS NULL)
                AND e."name" IS NULL
            """)
            result = db.execute(sql, {"name": name}).first()
            
            if not result:
                raise HTTPException(status_code=404, detail="여권 정보를 찾을 수 없습니다.")
            
            # 여권 정보 업데이트
            passport = db.query(Passport).filter(Passport.id == result[0]).first()
            if not passport:
                raise HTTPException(status_code=404, detail="여권 정보를 찾을 수 없습니다.")
            
            # 여권 정보 업데이트
            passport.name = new_name
            passport.passport_number = passport_number
            if birthday:
                passport.birthday = datetime.strptime(birthday, '%Y-%m-%d').date()
            
            # excel_data에서 새 이름으로 검색 (raw SQL 사용)
            sql = text("""
                SELECT "receiptNumber", name, "PayBack" 
                FROM excel_data 
                WHERE name = :name
            """)
            result = db.execute(sql, {"name": new_name}).first()
            
            # excel_data와 매칭되면 receipt_match_log 업데이트 및 여권 매칭 상태 업데이트
            if result:
                match_log = db.query(ReceiptMatchLog).filter(
                    ReceiptMatchLog.receipt_number == result[0]  # receiptNumber
                ).first()
                if match_log:
                    match_log.is_matched = True
                    match_log.excel_name = result[1]  # name
                    match_log.passport_number = passport_number
                    match_log.birthday = passport.birthday
                    # 여권 매칭 상태 업데이트
                    update_passport_matching_status(new_name, True)
            else:
                # 매칭되지 않은 경우 여권 매칭 상태를 False로 업데이트
                update_passport_matching_status(new_name, False)
            
            db.commit()
            
            # 성공 메시지와 함께 매칭안된 여권 목록 페이지로 리다이렉트
            return RedirectResponse(
                url="/unmatched-passports/",
                status_code=303
            )
            
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/unmatched-passports/")
async def unmatched_passports(request: Request):
    try:
        unmatched_passports = get_unmatched_passports()
        return templates.TemplateResponse(
            "unmatched_passports.html",
            {
                "request": request,
                "unmatched_passports": unmatched_passports
            }
        )
    except Exception as e:
        print(f"매칭안된 여권 목록 조회 중 오류 발생: {str(e)}")
        return templates.TemplateResponse(
            "unmatched_passports.html",
            {
                "request": request,
                "error": f"매칭안된 여권 목록 조회 중 오류가 발생했습니다: {str(e)}",
                "unmatched_passports": []
            }
        )