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
from fastapi.responses import JSONResponse

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

@router.post("/check-username/")
async def check_username(
    username: str = Form(...),
    db: Session = Depends(get_db)
):
    """아이디 중복체크 API"""
    try:
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            return JSONResponse(content={
                "available": False,
                "message": "이미 사용 중인 아이디입니다."
            })
        else:
            return JSONResponse(content={
                "available": True,
                "message": "사용 가능한 아이디입니다."
            })
    except Exception as e:
        return JSONResponse(content={
            "available": False,
            "message": "중복체크 중 오류가 발생했습니다."
        }, status_code=500)

@router.get("/login/")
def login_page(request: Request):
    """로그인 페이지"""
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/register/")
async def register_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...), 
    company_name: str = Form(...),
    position: str = Form(...),
    db: Session = Depends(get_db)
):
    """사용자 회원가입 신청"""
    try:
        # 아이디 중복 체크
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "error": "이미 존재하는 아이디입니다.",
                "username": username,
                "email": email,
                "company_name": company_name,
                "position": position
            })
        
        # 이메일 중복 체크
        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "error": "이미 존재하는 이메일입니다.",
                "username": username,
                "email": email,
                "company_name": company_name,
                "position": position
            })
        
        # 회사명 중복 체크
        if User.is_company_name_taken(company_name, db):
            return templates.TemplateResponse("register.html", {
                "request": request,
                "error": "이미 등록된 회사명입니다. 한 회사당 하나의 계정만 사용할 수 있습니다.",
                "username": username,
                "email": email,
                "company_name": company_name,
                "position": position
            })
        
        # 거절된 사용자 재신청 방지 체크
        rejected_user = db.query(User).filter(
            (User.username == username) | (User.email == email),
            User.status == "rejected"
        ).first()
        if rejected_user:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "error": "이미 가입이 거절된 계정입니다. 재가입이 불가합니다."
            })
        
        # 대기 중인 신청 체크
        pending_user = db.query(User).filter(
            (User.username == username) | (User.email == email),
            User.status == "pending"
        ).first()
        if pending_user:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "error": "이미 가입 신청이 진행 중입니다. 관리자 승인을 기다려주세요."
            })
        
        # 사용자 신청 생성 (비밀번호는 null, pending 상태)
        user = User(
            username=username,
            email=email,
            company_name=company_name,
            position=position,
            hashed_password=None,  # 승인 전까지는 null
            status="pending"
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # 관리자에게 신규 가입 알림 이메일 발송
        try:
            from app.services.email_service import email_service
            email_service.send_new_registration_notification(
                username=username,
                email=email,
                company_name=company_name,
                position=position
            )
            print(f"✅ 관리자 알림 이메일 발송 완료: {username}")
        except Exception as e:
            print(f"⚠️ 관리자 알림 이메일 발송 실패: {str(e)}")
        
        return templates.TemplateResponse("login.html", {
            "request": request,
            "success": "신규가입 신청이 완료되었습니다. 관리자 승인 후 이메일로 로그인 정보를 안내드립니다."
        })
        
    except Exception as e:
        db.rollback()
        print(f"회원가입 오류: {str(e)}")
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": f"회원가입 신청 중 오류가 발생했습니다: {str(e)}"
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
        
        # 사용자 존재 여부 확인
        if not user:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "존재하지 않는 사용자입니다."
            })
        
        # 승인 상태 확인
        if user.status == "pending":
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "아직 관리자 승인 대기 중입니다. 승인 후 이메일로 로그인 정보를 안내드립니다."
            })
        elif user.status == "rejected":
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "가입이 거절된 계정입니다."
            })
        elif user.status != "approved":
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "로그인할 수 없는 계정 상태입니다."
            })
        
        # 관리자는 일반 로그인 불가
        if user.is_admin:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "관리자는 관리자 페이지에서 로그인해 주세요."
            })
        
        # 비밀번호 확인
        if not user.hashed_password or not pwd_context.verify(password, user.hashed_password):
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "비밀번호가 잘못되었습니다."
            })
        
        # 최근 로그인 시간 업데이트
        from sqlalchemy import func
        user.last_login = func.now()
        db.commit()
        
        # JWT 토큰 생성
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, 
            expires_delta=access_token_expires
        )
        
        # 임시 비밀번호 사용자는 비밀번호 변경 페이지로 리다이렉트
        if user.is_temp_password:
            response = RedirectResponse(url="/auth/change-password", status_code=302)
        else:
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
        print(f"로그인 오류: {str(e)}")
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": f"로그인 중 오류가 발생했습니다: {str(e)}"
        })

@router.get("/logout/")
async def logout(response: Response):
    """사용자 로그아웃"""
    response.delete_cookie(key="access_token")
    return {"message": "로그아웃 성공"} 
