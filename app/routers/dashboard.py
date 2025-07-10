from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.models import User
from app.services import dashboard_service

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """대시보드 페이지를 렌더링합니다."""
    
    stats_data = dashboard_service.get_dashboard_stats(db=db, user_id=current_user.id)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user,
        "stats": stats_data
    })
