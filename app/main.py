from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.core.config import settings

# FastAPI 앱 생성
app = FastAPI(debug=True)

# 정적 파일 마운트
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
app.mount("/uploads", StaticFiles(directory=settings.uploads_dir, html=True), name="uploads")

# 기존 라우터들 등록
from app.routers import auth, api, upload
app.include_router(auth.router, tags=["인증"])
app.include_router(api.router, tags=["API"])
app.include_router(upload.router, tags=["업로드"])

# 새로 분리한 라우터들 등록
from app.routers import receipt, passport, history, fee, admin
app.include_router(receipt.router, tags=["영수증"])
app.include_router(passport.router, tags=["여권"])
app.include_router(history.router, tags=["이력관리"])
app.include_router(fee.router, tags=["수수료"])
app.include_router(admin.router, tags=["관리자"])