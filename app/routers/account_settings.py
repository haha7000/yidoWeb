"""
면세점 계정 설정 라우터
사용자별 롯데/신라 면세점 계정 정보 관리
"""
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import Optional

from app.models.models import User, DutyFreeAccount, AutomationLog
from app.core.auth import get_current_user, get_db
from app.core.config import settings
from app.services.account_verification import verification_service
from app.services.user_automation_service import automation_service

router = APIRouter()
templates = Jinja2Templates(directory=settings.templates_dir)

@router.get("/account-settings/")
def account_settings_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """면세점 계정 설정 페이지"""
    try:
        # 사용자의 기존 계정 정보 조회
        lotte_account = db.query(DutyFreeAccount).filter(
            and_(
                DutyFreeAccount.user_id == current_user.id,
                DutyFreeAccount.duty_free_type == "lotte"
            )
        ).first()
        
        shilla_account = db.query(DutyFreeAccount).filter(
            and_(
                DutyFreeAccount.user_id == current_user.id,
                DutyFreeAccount.duty_free_type == "shilla"
            )
        ).first()
        
        return templates.TemplateResponse("account_settings.html", {
            "request": request,
            "user": current_user,
            "lotte_account": lotte_account,
            "shilla_account": shilla_account
        })
        
    except Exception as e:
        print(f"계정 설정 페이지 로딩 오류: {e}")
        raise HTTPException(status_code=500, detail="페이지를 불러올 수 없습니다.")

@router.post("/account-settings/save/")
async def save_account_settings(
    duty_free_type: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    is_active: bool = Form(default=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """면세점 계정 정보 저장/업데이트"""
    try:
        # 입력값 검증
        if duty_free_type not in ["lotte", "shilla"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "올바르지 않은 면세점 타입입니다."}
            )
        
        if not username.strip() or not password.strip():
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "아이디와 비밀번호를 모두 입력해주세요."}
            )
        
        # 기존 계정 정보 확인
        existing_account = db.query(DutyFreeAccount).filter(
            and_(
                DutyFreeAccount.user_id == current_user.id,
                DutyFreeAccount.duty_free_type == duty_free_type
            )
        ).first()
        
        if existing_account:
            # 기존 계정 정보 업데이트
            existing_account.username = username.strip()
            existing_account.password = password.strip()
            existing_account.is_active = is_active
            existing_account.updated_at = func.now()
            action = "업데이트"
        else:
            # 새 계정 정보 생성
            new_account = DutyFreeAccount(
                user_id=current_user.id,
                duty_free_type=duty_free_type,
                username=username.strip(),
                password=password.strip(),
                is_active=is_active
            )
            db.add(new_account)
            action = "등록"
        
        db.commit()
        
        return JSONResponse(content={
            "success": True,
            "message": f"{duty_free_type.upper()} 계정이 성공적으로 {action}되었습니다."
        })
        
    except Exception as e:
        print(f"계정 저장 오류: {e}")
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "계정 저장 중 오류가 발생했습니다."}
        )

@router.post("/account-settings/test/")
async def test_account_login(
    duty_free_type: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """면세점 계정 로그인 테스트"""
    try:
        # 입력값 검증
        if duty_free_type not in ["lotte", "shilla"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "올바르지 않은 면세점 타입입니다."}
            )
        
        if not username.strip() or not password.strip():
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "아이디와 비밀번호를 모두 입력해주세요."}
            )
        
        # 실제 계정 검증 수행
        verification_result = await verification_service.verify_account(
            duty_free_type, username.strip(), password.strip()
        )
        
        return JSONResponse(content=verification_result)
        
    except Exception as e:
        print(f"계정 테스트 오류: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "계정 테스트 중 오류가 발생했습니다."}
        )

@router.delete("/account-settings/delete/{duty_free_type}")
async def delete_account_settings(
    duty_free_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """면세점 계정 정보 삭제"""
    try:
        if duty_free_type not in ["lotte", "shilla"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "올바르지 않은 면세점 타입입니다."}
            )
        
        # 계정 정보 조회
        account = db.query(DutyFreeAccount).filter(
            and_(
                DutyFreeAccount.user_id == current_user.id,
                DutyFreeAccount.duty_free_type == duty_free_type
            )
        ).first()
        
        if not account:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "삭제할 계정 정보가 없습니다."}
            )
        
        # 계정 정보 삭제
        db.delete(account)
        db.commit()
        
        return JSONResponse(content={
            "success": True,
            "message": f"{duty_free_type.upper()} 계정이 성공적으로 삭제되었습니다."
        })
        
    except Exception as e:
        print(f"계정 삭제 오류: {e}")
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "계정 삭제 중 오류가 발생했습니다."}
        )

@router.post("/account-settings/toggle/{duty_free_type}")
async def toggle_account_status(
    duty_free_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """면세점 계정 활성화/비활성화 토글"""
    try:
        if duty_free_type not in ["lotte", "shilla"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "올바르지 않은 면세점 타입입니다."}
            )
        
        # 계정 정보 조회
        account = db.query(DutyFreeAccount).filter(
            and_(
                DutyFreeAccount.user_id == current_user.id,
                DutyFreeAccount.duty_free_type == duty_free_type
            )
        ).first()
        
        if not account:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "계정 정보가 없습니다."}
            )
        
        # 활성화 상태 토글
        account.is_active = not account.is_active
        account.updated_at = func.now()
        db.commit()
        
        status_text = "활성화" if account.is_active else "비활성화"
        
        return JSONResponse(content={
            "success": True,
            "message": f"{duty_free_type.upper()} 계정이 {status_text}되었습니다.",
            "is_active": account.is_active
        })
        
    except Exception as e:
        print(f"계정 상태 변경 오류: {e}")
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "계정 상태 변경 중 오류가 발생했습니다."}
        )

@router.get("/automation-status/")
def automation_status_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """자동화 상태 확인 페이지"""
    try:
        # 사용자의 면세점 계정 정보 조회
        accounts = db.query(DutyFreeAccount).filter(
            DutyFreeAccount.user_id == current_user.id
        ).all()
        
        # 각 계정별 최근 자동화 로그 조회
        automation_status = {}
        for account in accounts:
            # 최근 10개의 로그 조회
            recent_logs = db.query(AutomationLog).filter(
                AutomationLog.account_id == account.id
            ).order_by(AutomationLog.started_at.desc()).limit(10).all()
            
            # 최근 성공한 로그
            last_success = db.query(AutomationLog).filter(
                and_(
                    AutomationLog.account_id == account.id,
                    AutomationLog.status == "success"
                )
            ).order_by(AutomationLog.started_at.desc()).first()
            
            automation_status[account.duty_free_type] = {
                "account": account,
                "recent_logs": recent_logs,
                "last_success": last_success,
                "total_success": db.query(AutomationLog).filter(
                    and_(
                        AutomationLog.account_id == account.id,
                        AutomationLog.status == "success"
                    )
                ).count(),
                "total_failed": db.query(AutomationLog).filter(
                    and_(
                        AutomationLog.account_id == account.id,
                        AutomationLog.status == "failed"
                    )
                ).count()
            }
        
        return templates.TemplateResponse("automation_status.html", {
            "request": request,
            "user": current_user,
            "automation_status": automation_status
        })
        
    except Exception as e:
        print(f"자동화 상태 페이지 로딩 오류: {e}")
        raise HTTPException(status_code=500, detail="페이지를 불러올 수 없습니다.")

@router.get("/api/automation-logs/{duty_free_type}")
async def get_automation_logs(
    duty_free_type: str,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """특정 면세점의 자동화 로그 조회 API"""
    try:
        if duty_free_type not in ["lotte", "shilla"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "올바르지 않은 면세점 타입입니다."}
            )
        
        # 사용자의 해당 면세점 계정 확인
        account = db.query(DutyFreeAccount).filter(
            and_(
                DutyFreeAccount.user_id == current_user.id,
                DutyFreeAccount.duty_free_type == duty_free_type
            )
        ).first()
        
        if not account:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "등록된 계정이 없습니다."}
            )
        
        # 로그 조회
        logs = db.query(AutomationLog).filter(
            AutomationLog.account_id == account.id
        ).order_by(AutomationLog.started_at.desc()).limit(limit).all()
        
        logs_data = []
        for log in logs:
            logs_data.append({
                "id": log.id,
                "status": log.status,
                "message": log.message,
                "records_count": log.records_count,
                "started_at": log.started_at.strftime('%Y-%m-%d %H:%M:%S') if log.started_at else None,
                "completed_at": log.completed_at.strftime('%Y-%m-%d %H:%M:%S') if log.completed_at else None,
                "duration": str(log.completed_at - log.started_at) if log.completed_at and log.started_at else None
            })
        
        return JSONResponse(content={
            "success": True,
            "logs": logs_data,
            "account": {
                "duty_free_type": account.duty_free_type,
                "username": account.username,
                "is_active": account.is_active
            }
        })
        
    except Exception as e:
        print(f"자동화 로그 조회 오류: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "로그 조회 중 오류가 발생했습니다."}
        )

@router.post("/api/run-automation/{duty_free_type}")
async def run_manual_automation(
    duty_free_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """특정 면세점의 수동 자동화 실행"""
    try:
        if duty_free_type not in ["lotte", "shilla"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "올바르지 않은 면세점 타입입니다."}
            )
        
        # 사용자의 해당 면세점 계정 확인
        account = db.query(DutyFreeAccount).filter(
            and_(
                DutyFreeAccount.user_id == current_user.id,
                DutyFreeAccount.duty_free_type == duty_free_type,
                DutyFreeAccount.is_active == True
            )
        ).first()
        
        if not account:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "활성화된 계정이 없습니다."}
            )
        
        # 자동화 실행
        if duty_free_type == "lotte":
            result = await automation_service.run_lotte_automation(account)
        else:
            result = await automation_service.run_shilla_automation(account)
        
        return JSONResponse(content=result)
        
    except Exception as e:
        print(f"수동 자동화 실행 오류: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "자동화 실행 중 오류가 발생했습니다."}
        )