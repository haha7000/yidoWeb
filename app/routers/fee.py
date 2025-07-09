from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from app.core.auth import get_current_user
from app.models.models import User
from app.core.config import settings

router = APIRouter()
templates = Jinja2Templates(directory=settings.templates_dir)

@router.get("/fee/", response_class=HTMLResponse)
async def fee_management_page(request: Request, current_user: User = Depends(get_current_user)):
    """수수료 적용기준 관리 페이지"""
    return templates.TemplateResponse("fee.html", {
        "request": request,
        "user": current_user
    })