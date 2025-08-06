from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import my_engine
from app.models.models import Base
from app.routers import auth, api, upload
from app.routers import receipt, passport, history, fee, admin, result_management

# FastAPI 앱 생성
app = FastAPI(debug=True)

# 서버 시작 시 데이터베이스 테이블 자동 생성
@app.on_event("startup")
async def startup_event():
    """서버 시작 시 데이터베이스 테이블을 자동으로 생성합니다."""
    try:
        # 모든 모델의 테이블을 생성
        Base.metadata.create_all(bind=my_engine)
        print("✅ 데이터베이스 테이블이 성공적으로 생성되었습니다.")
    except Exception as e:
        print(f"❌ 데이터베이스 테이블 생성 중 오류가 발생했습니다: {e}")
        raise e

# 정적 파일 마운트
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
app.mount("/uploads", StaticFiles(directory=settings.uploads_dir, html=True), name="uploads")
app.include_router(auth.router, tags=["인증"])
app.include_router(api.router, tags=["API"])
app.include_router(upload.router, tags=["업로드"])
app.include_router(receipt.router, tags=["영수증"])
app.include_router(passport.router, tags=["여권"])
app.include_router(history.router, tags=["이력관리"])
app.include_router(fee.router, tags=["수수료"])
app.include_router(admin.router, tags=["관리자"])
app.include_router(result_management.router, tags=["결과관리"])