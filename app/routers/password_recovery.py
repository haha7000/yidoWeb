"""
비밀번호 복구 관련 라우터 (아이디 찾기, 비밀번호 찾기, 비밀번호 변경)
"""
from fastapi import APIRouter, Request, Depends, Form, HTTPException, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from passlib.context import CryptContext

from app.models.models import User
from app.core.auth import get_db, get_current_user_optional
from app.core.config import settings
from app.services.email_service import email_service

router = APIRouter()
templates = Jinja2Templates(directory=settings.templates_dir)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def validate_password(password: str) -> tuple[bool, str]:
    """비밀번호 유효성 검사"""
    if len(password) < 8:
        return False, "비밀번호는 최소 8자리 이상이어야 합니다."
    if len(password) > 20:
        return False, "비밀번호는 최대 20자리까지 입력 가능합니다."
    return True, ""

@router.get("/auth/find-username")
def find_username_page(request: Request):
    """아이디 찾기 페이지"""
    return templates.TemplateResponse("auth/find_username.html", {"request": request})

@router.post("/auth/find-username/")
async def find_username_process(
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    """아이디 찾기 처리"""
    try:
        # 이메일로 사용자 검색
        user = db.query(User).filter(User.email == email).first()
        
        if user and user.status == "approved":
            # 이메일 발송
            email_sent = email_service.send_username_recovery_email(
                user_email=user.email,
                username=user.username,
                company_name=user.company_name
            )
            
            if email_sent:
                return JSONResponse(content={
                    "success": True,
                    "message": "입력하신 이메일로 아이디 정보를 발송했습니다. 이메일을 확인해 주세요."
                })
            else:
                return JSONResponse(content={
                    "success": False,
                    "message": "이메일 발송 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
                })
        else:
            # 보안상 동일한 메시지 반환 (사용자 존재 여부 숨김)
            return JSONResponse(content={
                "success": True,
                "message": "입력하신 이메일로 아이디 정보를 발송했습니다. 이메일을 확인해 주세요."
            })
            
    except Exception as e:
        print(f"아이디 찾기 오류: {str(e)}")
        return JSONResponse(content={
            "success": False,
            "message": "시스템 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        })

@router.get("/auth/find-password")
def find_password_page(request: Request):
    """비밀번호 찾기 페이지"""
    return templates.TemplateResponse("auth/find_password.html", {"request": request})

@router.post("/auth/find-password/")
async def find_password_process(
    username: str = Form(...),
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    """비밀번호 찾기 처리 (재설정 링크 발송)"""
    try:
        # 사용자 검색 (아이디 + 이메일 일치)
        user = db.query(User).filter(
            User.username == username,
            User.email == email
        ).first()
        
        if user and user.status == "approved":
            # 재설정 토큰 생성
            reset_token = user.generate_reset_token()
            db.commit()
            
            # 재설정 링크 이메일 발송
            email_sent = email_service.send_password_reset_email(
                user_email=user.email,
                username=user.username,
                company_name=user.company_name,
                reset_token=reset_token
            )
            
            if email_sent:
                return JSONResponse(content={
                    "success": True,
                    "message": "비밀번호 재설정 링크를 이메일로 발송했습니다. 이메일을 확인해 주세요."
                })
            else:
                return JSONResponse(content={
                    "success": False,
                    "message": "이메일 발송 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
                })
        else:
            # 보안상 동일한 메시지 반환
            return JSONResponse(content={
                "success": True,
                "message": "비밀번호 재설정 링크를 이메일로 발송했습니다. 이메일을 확인해 주세요."
            })
            
    except Exception as e:
        print(f"비밀번호 찾기 오류: {str(e)}")
        return JSONResponse(content={
            "success": False,
            "message": "시스템 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        })

@router.get("/auth/reset-password")
def reset_password_page(request: Request, token: str = Query(...)):
    """비밀번호 재설정 페이지"""
    return templates.TemplateResponse("auth/reset_password.html", {
        "request": request,
        "token": token
    })

@router.post("/auth/reset-password/")
async def reset_password_process(
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    """비밀번호 재설정 처리"""
    try:
        # 비밀번호 확인
        if new_password != confirm_password:
            return JSONResponse(content={
                "success": False,
                "message": "새 비밀번호와 확인 비밀번호가 일치하지 않습니다."
            })
        
        # 비밀번호 유효성 검사
        is_valid, error_message = validate_password(new_password)
        if not is_valid:
            return JSONResponse(content={
                "success": False,
                "message": error_message
            })
        
        # 토큰으로 사용자 검색
        user = db.query(User).filter(User.reset_token == token).first()
        
        if not user:
            return JSONResponse(content={
                "success": False,
                "message": "유효하지 않은 재설정 링크입니다."
            })
        
        # 토큰 유효성 검사
        if not user.is_reset_token_valid(token):
            return JSONResponse(content={
                "success": False,
                "message": "재설정 링크가 만료되었습니다. 다시 요청해 주세요."
            })
        
        # 비밀번호 업데이트
        user.hashed_password = pwd_context.hash(new_password)
        user.is_temp_password = False  # 더 이상 임시 비밀번호가 아님
        user.clear_reset_token()  # 토큰 삭제
        
        db.commit()
        
        return JSONResponse(content={
            "success": True,
            "message": "비밀번호가 성공적으로 변경되었습니다. 새 비밀번호로 로그인해 주세요."
        })
        
    except Exception as e:
        db.rollback()
        print(f"비밀번호 재설정 오류: {str(e)}")
        return JSONResponse(content={
            "success": False,
            "message": "시스템 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        })

@router.get("/auth/change-password")
def change_password_page(request: Request, user: User = Depends(get_current_user_optional)):
    """비밀번호 변경 페이지 (로그인 후 사용자용)"""
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("auth/change_password.html", {
        "request": request,
        "user": user,
        "is_temp_password": user.is_temp_password
    })

@router.post("/auth/change-password/")
async def change_password_process(
    request: Request,
    current_password: str = Form(None),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """비밀번호 변경 처리"""
    try:
        if not user:
            return JSONResponse(content={
                "success": False,
                "message": "로그인이 필요합니다."
            })
        
        # 비밀번호 확인
        if new_password != confirm_password:
            return JSONResponse(content={
                "success": False,
                "message": "새 비밀번호와 확인 비밀번호가 일치하지 않습니다."
            })
        
        # 비밀번호 유효성 검사
        is_valid, error_message = validate_password(new_password)
        if not is_valid:
            return JSONResponse(content={
                "success": False,
                "message": error_message
            })
        
        # 임시 비밀번호가 아닌 경우 현재 비밀번호 확인
        if not user.is_temp_password:
            if not current_password:
                return JSONResponse(content={
                    "success": False,
                    "message": "현재 비밀번호를 입력해 주세요."
                })
            
            if not user.verify_password(current_password):
                return JSONResponse(content={
                    "success": False,
                    "message": "현재 비밀번호가 올바르지 않습니다."
                })
        
        # 비밀번호 업데이트
        user.hashed_password = pwd_context.hash(new_password)
        user.is_temp_password = False  # 더 이상 임시 비밀번호가 아님
        
        db.commit()
        
        return JSONResponse(content={
            "success": True,
            "message": "비밀번호가 성공적으로 변경되었습니다."
        })
        
    except Exception as e:
        db.rollback()
        print(f"비밀번호 변경 오류: {str(e)}")
        return JSONResponse(content={
            "success": False,
            "message": "시스템 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        })