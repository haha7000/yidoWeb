"""
관리자 시스템 라우터
"""
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from datetime import timedelta, datetime
from passlib.context import CryptContext

from app.models.models import User
from app.core.auth import get_db, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.core.config import settings
from app.services.email_service import email_service

router = APIRouter()
templates = Jinja2Templates(directory=settings.templates_dir)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_admin_user(request: Request, db: Session = Depends(get_db)) -> User:
    """관리자 인증 확인"""
    token = request.cookies.get("admin_access_token")
    if not token:
        raise HTTPException(status_code=401, detail="관리자 로그인이 필요합니다")
    
    try:
        from jose import jwt
        from app.core.config import settings
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    return user

@router.get("/admin/login")
def admin_login_page(request: Request):
    """관리자 로그인 페이지"""
    return templates.TemplateResponse("admin/admin_login.html", {"request": request})

@router.post("/admin/login/")
async def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """관리자 로그인"""
    try:
        # 사용자 확인
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            return templates.TemplateResponse("admin/admin_login.html", {
                "request": request,
                "error": "존재하지 않는 관리자입니다."
            })
        
        # 관리자 권한 확인
        if not user.is_admin:
            return templates.TemplateResponse("admin/admin_login.html", {
                "request": request,
                "error": "관리자 권한이 없습니다."
            })
        
        # 비밀번호 확인
        if not user.hashed_password or not pwd_context.verify(password, user.hashed_password):
            return templates.TemplateResponse("admin/admin_login.html", {
                "request": request,
                "error": "비밀번호가 잘못되었습니다."
            })
        
        # 최근 로그인 시간 업데이트
        user.last_login = func.now()
        db.commit()
        
        # JWT 토큰 생성
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, 
            expires_delta=access_token_expires
        )
        
        # 쿠키에 토큰 저장하고 관리자 대시보드로 리다이렉트
        response = RedirectResponse(url="/admin/dashboard", status_code=302)
        response.set_cookie(
            key="admin_access_token",
            value=access_token,
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax"
        )
        
        return response
        
    except Exception as e:
        print(f"관리자 로그인 오류: {str(e)}")
        return templates.TemplateResponse("admin/admin_login.html", {
            "request": request,
            "error": f"로그인 중 오류가 발생했습니다: {str(e)}"
        })

@router.get("/admin/dashboard")
async def admin_dashboard(
    request: Request,
    tab: str = "pending",
    current_admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """관리자 대시보드"""
    try:
        # 신규 신청 사용자 조회
        pending_users = db.query(User).filter(User.status == "pending").order_by(User.created_at.desc()).all()
        
        # 승인된 사용자 조회 (관리자 제외)
        approved_users = db.query(User).filter(
            User.status == "approved",
            User.is_admin == False
        ).order_by(User.created_at.desc()).all()
        
        # 통계 정보
        stats = {
            "pending_count": len(pending_users),
            "approved_count": len(approved_users),
            "rejected_count": db.query(User).filter(User.status == "rejected").count(),
            "total_count": db.query(User).filter(User.is_admin == False).count()
        }
        
        return templates.TemplateResponse("admin/admin_dashboard.html", {
            "request": request,
            "current_tab": tab,
            "pending_users": pending_users,
            "approved_users": approved_users,
            "stats": stats,
            "admin": current_admin
        })
        
    except Exception as e:
        print(f"관리자 대시보드 오류: {str(e)}")
        raise HTTPException(status_code=500, detail="대시보드 로딩 중 오류가 발생했습니다")

@router.post("/admin/approve-user/")
async def approve_user(
    user_id: int = Form(...),
    current_admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """사용자 승인"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return JSONResponse(content={"success": False, "message": "사용자를 찾을 수 없습니다."})
        
        if user.status != "pending":
            return JSONResponse(content={"success": False, "message": "승인 대기 상태가 아닌 사용자입니다."})
        
        # 랜덤 비밀번호 생성
        random_password = email_service.generate_random_password()
        hashed_password = pwd_context.hash(random_password)
        
        # 사용자 상태 업데이트
        user.status = "approved"
        user.hashed_password = hashed_password
        user.approved_at = func.now()
        user.approved_by = current_admin.id
        
        db.commit()
        
        # 비밀번호 발송 이메일
        email_sent = email_service.send_password_email(
            user_email=user.email,
            username=user.username,
            password=random_password,
            company_name=user.company_name
        )
        
        if email_sent:
            return JSONResponse(content={
                "success": True, 
                "message": f"{user.username} 사용자가 승인되었습니다. 이메일이 발송되었습니다."
            })
        else:
            # 이메일 발송 실패해도 승인은 유지
            return JSONResponse(content={
                "success": True, 
                "message": f"{user.username} 사용자가 승인되었습니다. (이메일 발송 실패)",
                "warning": True
            })
        
    except Exception as e:
        db.rollback()
        print(f"사용자 승인 오류: {str(e)}")
        return JSONResponse(content={"success": False, "message": f"승인 처리 중 오류가 발생했습니다: {str(e)}"})

@router.post("/admin/reject-user/")
async def reject_user(
    user_id: int = Form(...),
    current_admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """사용자 거절"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return JSONResponse(content={"success": False, "message": "사용자를 찾을 수 없습니다."})
        
        if user.status != "pending":
            return JSONResponse(content={"success": False, "message": "승인 대기 상태가 아닌 사용자입니다."})
        
        # 사용자 상태 업데이트
        user.status = "rejected"
        user.approved_by = current_admin.id
        
        db.commit()
        
        # 거절 알림 이메일 발송
        email_service.send_rejection_notification(
            user_email=user.email,
            username=user.username,
            company_name=user.company_name
        )
        
        return JSONResponse(content={
            "success": True, 
            "message": f"{user.username} 사용자의 가입이 거절되었습니다."
        })
        
    except Exception as e:
        db.rollback()
        print(f"사용자 거절 오류: {str(e)}")
        return JSONResponse(content={"success": False, "message": f"거절 처리 중 오류가 발생했습니다: {str(e)}"})

@router.post("/admin/deactivate-user/")
async def deactivate_user(
    user_id: int = Form(...),
    current_admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """사용자 탈퇴 처리"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return JSONResponse(content={"success": False, "message": "사용자를 찾을 수 없습니다."})
        
        if user.is_admin:
            return JSONResponse(content={"success": False, "message": "관리자 계정은 탈퇴시킬 수 없습니다."})
        
        # 사용자 비활성화
        user.is_active = False
        user.status = "deactivated"
        
        db.commit()
        
        return JSONResponse(content={
            "success": True, 
            "message": f"{user.username} 사용자가 탈퇴 처리되었습니다."
        })
        
    except Exception as e:
        db.rollback()
        print(f"사용자 탈퇴 오류: {str(e)}")
        return JSONResponse(content={"success": False, "message": f"탈퇴 처리 중 오류가 발생했습니다: {str(e)}"})

@router.get("/admin/search-users/")
async def search_users(
    q: str = "",
    tab: str = "approved",
    current_admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """사용자 검색 API"""
    try:
        query = db.query(User).filter(User.is_admin == False)
        
        if tab == "pending":
            query = query.filter(User.status == "pending")
        elif tab == "approved":
            query = query.filter(User.status == "approved")
        
        if q:
            # 아이디, 이메일, 회사명, 직책으로 검색
            search_term = f"%{q}%"
            query = query.filter(
                (User.username.ilike(search_term)) |
                (User.email.ilike(search_term)) |
                (User.company_name.ilike(search_term)) |
                (User.position.ilike(search_term))
            )
        
        users = query.order_by(User.created_at.desc()).all()
        
        # JSON 형태로 변환
        users_data = []
        for user in users:
            users_data.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "company_name": user.company_name,
                "position": user.position,
                "status": user.status,
                "created_at": user.created_at.strftime('%Y-%m-%d %H:%M') if user.created_at else "",
                "last_login": user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else "로그인 기록 없음",
                "approved_at": user.approved_at.strftime('%Y-%m-%d %H:%M') if user.approved_at else ""
            })
        
        return JSONResponse(content={"users": users_data})
        
    except Exception as e:
        print(f"사용자 검색 오류: {str(e)}")
        return JSONResponse(content={"error": "검색 중 오류가 발생했습니다"}, status_code=500)

@router.get("/admin/logout/")
async def admin_logout():
    """관리자 로그아웃"""
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie(key="admin_access_token")
    return response