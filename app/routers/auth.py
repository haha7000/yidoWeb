"""
인증 관련 라우터
"""
from fastapi import APIRouter, Request, Form, Depends, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import timedelta
from passlib.context import CryptContext

from app.models.models import User
from app.core.auth import get_current_user_optional, get_db, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.core.config import settings

router = APIRouter()
templates = Jinja2Templates(directory=settings.templates_dir)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.get("/")
def main_page(request: Request, db: Session = Depends(get_db)):
    """메인 페이지 - 로그인된 사용자는 업로드 페이지로 리다이렉트"""
    user = get_current_user_optional(request, db)
    if user:
        return RedirectResponse(url="/upload/", status_code=302)
    
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/register")
def register_page(request: Request):
    """회원가입 페이지"""
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register/")
async def register_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...), 
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """사용자 회원가입"""
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
        
        return templates.TemplateResponse("login.html", {
            "request": request,
            "success": "회원가입이 완료되었습니다. 로그인해주세요."
        })
        
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": f"회원가입 중 오류가 발생했습니다: {str(e)}"
        })

@router.post("/login/")
async def login_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """사용자 로그인"""
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

@router.get("/logout/")
async def logout(response: Response):
    """사용자 로그아웃"""
    response.delete_cookie(key="access_token")
    return {"message": "로그아웃 성공"} 