from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from app.core.auth import get_current_user
from app.models.models import User
from app.core.config import settings
from app.core.database import SessionLocal
from sqlalchemy import text
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory=settings.templates_dir)

@router.get("/fee/", response_class=HTMLResponse)
async def fee_management_page(request: Request, current_user: User = Depends(get_current_user)):
    """수수료 적용기준 관리 페이지"""
    return templates.TemplateResponse("fee.html", {
        "request": request,
        "user": current_user
    })

@router.get("/api/fees/uploaded/")
async def get_uploaded_fees(current_user: User = Depends(get_current_user)):
    """사용자가 업로드한 수수료 설정 목록 조회"""
    try:
        with SessionLocal() as db:
            query = """
            SELECT 
                id,
                company_name,
                branch_name,
                effective_from,
                effective_to,
                free_rate_threshold,
                created_at,
                creator_id,
                note
            FROM fee_settings 
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            """
            
            result = db.execute(text(query), {"user_id": current_user.id}).fetchall()
            
            fee_settings = []
            for row in result:
                fee_settings.append({
                    "id": row.id,
                    "company_name": row.company_name,
                    "branch_name": row.branch_name,
                    "effective_from": row.effective_from.strftime("%Y-%m-%d") if row.effective_from else None,
                    "effective_to": row.effective_to.strftime("%Y-%m-%d") if row.effective_to else None,
                    "free_rate_threshold": float(row.free_rate_threshold * 100) if row.free_rate_threshold else 0.0,  # 백분율로 변환
                    "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S") if row.created_at else None,
                    "note": row.note
                })
            
            return JSONResponse({
                "success": True,
                "data": fee_settings,
                "count": len(fee_settings)
            })
            
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": f"수수료 목록 조회 중 오류가 발생했습니다: {str(e)}"
        }, status_code=500)

@router.delete("/api/fees/uploaded/")
async def delete_uploaded_fees(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """선택된 수수료 설정들을 삭제"""
    try:
        # 요청 body에서 삭제할 ID 목록 받기
        body = await request.json()
        fee_ids = body.get("fee_ids", [])
        
        if not fee_ids:
            return JSONResponse({
                "success": False,
                "message": "삭제할 수수료 설정을 선택해주세요."
            }, status_code=400)
        
        with SessionLocal() as db:
            # 사용자 권한 확인 및 삭제
            for fee_id in fee_ids:
                # 1. fee_settings 확인 및 권한 체크
                check_query = """
                SELECT id FROM fee_settings 
                WHERE id = :fee_id AND user_id = :user_id
                """
                
                result = db.execute(text(check_query), {
                    "fee_id": fee_id,
                    "user_id": current_user.id
                }).first()
                
                if not result:
                    return JSONResponse({
                        "success": False,
                        "message": f"권한이 없거나 존재하지 않는 수수료 설정입니다: {fee_id}"
                    }, status_code=403)
                
                # 2. 관련 데이터 삭제 (순서 중요: 외래키 제약)
                # exempt_brands 삭제
                db.execute(text("DELETE FROM exempt_brands WHERE settings_id = :fee_id"), {"fee_id": fee_id})
                
                # item_fees 삭제
                db.execute(text("DELETE FROM item_fees WHERE settings_id = :fee_id"), {"fee_id": fee_id})
                
                # brand_fees 삭제
                db.execute(text("DELETE FROM brand_fees WHERE settings_id = :fee_id"), {"fee_id": fee_id})
                
                # category_fees 삭제
                db.execute(text("DELETE FROM category_fees WHERE settings_id = :fee_id"), {"fee_id": fee_id})
                
                # fee_settings 삭제
                db.execute(text("DELETE FROM fee_settings WHERE id = :fee_id"), {"fee_id": fee_id})
            
            db.commit()
            
            return JSONResponse({
                "success": True,
                "message": f"{len(fee_ids)}개의 수수료 설정이 성공적으로 삭제되었습니다.",
                "deleted_count": len(fee_ids)
            })
            
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": f"수수료 설정 삭제 중 오류가 발생했습니다: {str(e)}"
        }, status_code=500)

@router.get("/api/fees/settings/{settings_id}")
async def get_fee_setting_detail(
    settings_id: int,
    current_user: User = Depends(get_current_user)
):
    """특정 수수료 설정의 상세 정보 조회"""
    try:
        with SessionLocal() as db:
            # 1. 권한 확인 및 기본 설정 조회
            settings_query = """
            SELECT 
                id,
                company_name,
                branch_name,
                effective_from,
                effective_to,
                free_rate_threshold,
                created_at,
                creator_id,
                note
            FROM fee_settings 
            WHERE id = :settings_id AND user_id = :user_id
            """
            
            settings_result = db.execute(text(settings_query), {
                "settings_id": settings_id,
                "user_id": current_user.id
            }).first()
            
            if not settings_result:
                return JSONResponse({
                    "success": False,
                    "message": "권한이 없거나 존재하지 않는 수수료 설정입니다."
                }, status_code=403)
            
            # 2. 카테고리별 수수료 조회
            category_query = """
            SELECT id, fee_type, commission_rate, created_at
            FROM category_fees 
            WHERE settings_id = :settings_id
            ORDER BY 
                CASE fee_type 
                    WHEN '일반' THEN 1
                    WHEN '토산 화장품' THEN 2  
                    WHEN '수입 화장품' THEN 3
                    WHEN '주류' THEN 4
                    WHEN '담배' THEN 5
                    WHEN '식품' THEN 6
                    WHEN '전자기기' THEN 7
                    ELSE 8
                END
            """
            category_results = db.execute(text(category_query), {"settings_id": settings_id}).fetchall()
            
            # 3. 브랜드별 수수료 조회
            brand_query = """
            SELECT id, category_code, category_name, import_type, brand_name, commission_rate, created_at
            FROM brand_fees 
            WHERE settings_id = :settings_id
            ORDER BY category_code, brand_name
            """
            brand_results = db.execute(text(brand_query), {"settings_id": settings_id}).fetchall()
            
            # 4. 품목별 수수료 조회
            item_query = """
            SELECT id, category_code, category_name, import_type, brand_name, item_name, product_code, commission_rate, created_at
            FROM item_fees 
            WHERE settings_id = :settings_id
            ORDER BY category_code, brand_name, product_code
            """
            item_results = db.execute(text(item_query), {"settings_id": settings_id}).fetchall()
            
            # 5. 수수료 제외 브랜드 조회
            exempt_query = """
            SELECT id, category_code, category_name, import_type, brand_name, created_at
            FROM exempt_brands 
            WHERE settings_id = :settings_id
            ORDER BY category_code, brand_name
            """
            exempt_results = db.execute(text(exempt_query), {"settings_id": settings_id}).fetchall()
            
            # 6. 응답 데이터 구성
            response_data = {
                "settings": {
                    "id": settings_result.id,
                    "company_name": settings_result.company_name,
                    "branch_name": settings_result.branch_name,
                    "effective_from": settings_result.effective_from.strftime("%Y-%m-%d") if settings_result.effective_from else None,
                    "effective_to": settings_result.effective_to.strftime("%Y-%m-%d") if settings_result.effective_to else None,
                    "free_rate_threshold": float(settings_result.free_rate_threshold) if settings_result.free_rate_threshold else 0.0,
                    "created_at": settings_result.created_at.strftime("%Y-%m-%d %H:%M:%S") if settings_result.created_at else None,
                    "note": settings_result.note
                },
                "category_fees": [{
                    "id": row.id,
                    "fee_type": row.fee_type,
                    "commission_rate": float(row.commission_rate),
                    "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S") if row.created_at else None
                } for row in category_results],
                "brand_fees": [{
                    "id": row.id,
                    "category_code": row.category_code,
                    "category_name": row.category_name,
                    "import_type": row.import_type,
                    "brand_name": row.brand_name,
                    "commission_rate": float(row.commission_rate),
                    "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S") if row.created_at else None
                } for row in brand_results],
                "item_fees": [{
                    "id": row.id,
                    "category_code": row.category_code,
                    "category_name": row.category_name,
                    "import_type": row.import_type,
                    "brand_name": row.brand_name,
                    "item_name": row.item_name,
                    "product_code": row.product_code,
                    "commission_rate": float(row.commission_rate),
                    "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S") if row.created_at else None
                } for row in item_results],
                "exempt_brands": [{
                    "id": row.id,
                    "category_code": row.category_code,
                    "category_name": row.category_name,
                    "import_type": row.import_type,
                    "brand_name": row.brand_name,
                    "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S") if row.created_at else None
                } for row in exempt_results]
            }
            
            return JSONResponse({
                "success": True,
                "data": response_data,
                **response_data  # 호환성을 위해 최상위에도 포함
            })
            
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": f"수수료 설정 조회 중 오류가 발생했습니다: {str(e)}"
        }, status_code=500)

@router.put("/api/fees/settings/{settings_id}")
async def update_fee_settings(
    settings_id: int,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """수수료 설정 정보 수정"""
    try:
        # 요청 body에서 수정할 데이터 받기
        body = await request.json()
        
        with SessionLocal() as db:
            # 1. 권한 확인
            check_query = """
            SELECT id FROM fee_settings 
            WHERE id = :settings_id AND user_id = :user_id
            """
            
            result = db.execute(text(check_query), {
                "settings_id": settings_id,
                "user_id": current_user.id
            }).first()
            
            if not result:
                return JSONResponse({
                    "success": False,
                    "message": "권한이 없거나 존재하지 않는 수수료 설정입니다."
                }, status_code=403)
            
            # 2. 수정할 필드들 구성
            update_fields = []
            params = {"settings_id": settings_id}
            
            if "company_name" in body:
                update_fields.append("company_name = :company_name")
                params["company_name"] = body["company_name"]
            
            if "branch_name" in body:
                update_fields.append("branch_name = :branch_name")
                params["branch_name"] = body["branch_name"]
            
            if "effective_from" in body:
                update_fields.append("effective_from = :effective_from")
                params["effective_from"] = body["effective_from"]
            
            if "effective_to" in body:
                update_fields.append("effective_to = :effective_to")
                params["effective_to"] = body["effective_to"]
            
            if "note" in body:
                update_fields.append("note = :note")
                params["note"] = body["note"]
            
            if not update_fields:
                return JSONResponse({
                    "success": False,
                    "message": "수정할 데이터가 없습니다."
                }, status_code=400)
            
            # 3. 업데이트 실행
            update_query = f"""
            UPDATE fee_settings 
            SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = :settings_id
            """
            
            db.execute(text(update_query), params)
            db.commit()
            
            return JSONResponse({
                "success": True,
                "message": "수수료 설정이 성공적으로 수정되었습니다."
            })
            
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": f"수수료 설정 수정 중 오류가 발생했습니다: {str(e)}"
        }, status_code=500)