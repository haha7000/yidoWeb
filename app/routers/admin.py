from fastapi import APIRouter, Request, HTTPException, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from app.services.passportMatching import matching_passport
from app.services.matching import fetch_results
from app.routers.upload import calculate_fully_matched_customers, calculate_passport_statistics
from app.core.database import SessionLocal
from app.models.models import User, Receipt, Passport, ReceiptMatchLog, ShillaReceipt, UnrecognizedImage
from app.services.receipt_service import ReceiptService
from datetime import datetime
from sqlalchemy.sql import text as sql_text
from sqlalchemy.orm import Session
from app.core.auth import get_current_user, get_db
from app.core.config import settings

router = APIRouter()
templates = Jinja2Templates(directory=settings.templates_dir)

@router.get("/result/")
async def get_result(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # 사용자의 마지막 처리 타입을 확인
        duty_free_type = "lotte"  # 기본값
        
        # 먼저 신라 데이터가 있는지 확인
        try:
            shilla_count_sql = sql_text("""
                SELECT COUNT(*) FROM shilla_receipts 
                WHERE user_id = :user_id
            """)
            shilla_count = db.execute(shilla_count_sql, {"user_id": current_user.id}).scalar()
            
            if shilla_count > 0:
                duty_free_type = "shilla"
                print(f"신라 영수증 {shilla_count}개 발견, 신라 모드로 설정")
            else:
                # 롯데 데이터 확인
                lotte_count_sql = sql_text("""
                    SELECT COUNT(*) FROM receipts 
                    WHERE user_id = :user_id
                """)
                lotte_count = db.execute(lotte_count_sql, {"user_id": current_user.id}).scalar()
                
                if lotte_count > 0:
                    duty_free_type = "lotte"
                    print(f"롯데 영수증 {lotte_count}개 발견, 롯데 모드로 설정")
                
        except Exception as e:
            print(f"테이블 조회 오류: {e}")
            # 테이블이 없는 경우 기본값 유지
        
        print(f"결과 조회 - 사용자: {current_user.id}, 면세점 타입: {duty_free_type}")
        
        # 📌 매칭 로직 자동 실행 (데이터 일관성 유지를 위해 활성화)
        print("🔄 매칭 로직 자동 실행 중...")
        try:
            if duty_free_type == "shilla":
                from app.services.shilla_matching import shilla_matching_result
                print("🔄 신라 매칭 로직 자동 실행 중...")
                shilla_matching_result(current_user.id)
                print("✅ 신라 매칭 로직 완료")
            else:
                from app.services.matching import matchingResult
                print("🔄 롯데 매칭 로직 자동 실행 중...")
                matchingResult(current_user.id)
                print("✅ 롯데 매칭 로직 완료")
        except Exception as e:
            print(f"⚠️ 매칭 로직 실행 중 오류: {e}")
        
        # 📌 매칭 완료 후 자동으로 수수료 계산 실행
        print("💰 결과 페이지 새로고침 - 자동 수수료 계산 시작...")
        try:
            from app.services.commission_service import calculate_discounts_and_commissions
            from sqlalchemy import text
            
            # sales_date 업데이트 (롯데의 경우)
            if duty_free_type == "lotte":
                print("📅 롯데 데이터 sales_date 업데이트 중...")
                try:
                    update_result = db.execute(sql_text('''
                        UPDATE receipt_match_log 
                        SET sales_date = (
                            SELECT DATE(led."매출일자")
                            FROM lotte_excel_data led
                            WHERE led."receiptNumber" = receipt_match_log.receipt_number
                            LIMIT 1
                        )
                        WHERE duty_free_type = 'lotte' 
                        AND is_matched = TRUE 
                        AND sales_date IS NULL
                        AND user_id = :user_id
                    '''), {"user_id": current_user.id}).rowcount
                    
                    db.commit()
                    if update_result > 0:
                        print(f"📅 sales_date 업데이트 완료: {update_result}개")
                except Exception as update_error:
                    print(f"⚠️ sales_date 업데이트 중 오류: {update_error}")
                    db.rollback()
            
            # 수수료 계산 실행
            commission_result = calculate_discounts_and_commissions(user_id=current_user.id)
            if commission_result["success"]:
                if commission_result['processed_count'] > 0:
                    print(f"✅ 자동 수수료 계산 완료: {commission_result['processed_count']}개 처리")
                else:
                    print("✅ 수수료 계산 완료 (신규 처리할 데이터 없음)")
            else:
                print(f"⚠️ 자동 수수료 계산 실패: {commission_result['message']}")
        except Exception as e:
            print(f"⚠️ 자동 수수료 계산 중 오류: {e}")
        
        # 매칭된/안된 목록 조회
        matched, unmatched = fetch_results(current_user.id, duty_free_type)
        # 여권 정보 조회
        passport_info = matching_passport(current_user.id, duty_free_type)
        
        # 영수증과 여권이 모두 매칭된 고객 수 계산
        fully_matched_customers = calculate_fully_matched_customers(current_user.id, duty_free_type, db)
        
        # 여권 통계 계산
        passport_stats = calculate_passport_statistics(current_user.id, duty_free_type, db)
        
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "results": passport_info,
                "unmatched_receipts": unmatched,
                "fully_matched_customers": fully_matched_customers,
                "passport_stats": passport_stats,
                "user": current_user,
                "duty_free_type": duty_free_type
            }
        )
    except Exception as e:
        print(f"결과 조회 중 오류 발생: {str(e)}")
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "error": f"결과 조회 중 오류가 발생했습니다: {str(e)}",
                "results": [],
                "unmatched_receipts": [],
                "fully_matched_customers": 0,
                "passport_stats": {"total_passports": 0, "matched_passports": 0, "unmatched_passports": 0},
                "user": current_user,
                "duty_free_type": "lotte"
            }
        )

@router.post("/api/change-type/")
async def change_item_type(
    item_id: int = Form(...),
    current_type: str = Form(...),  # "receipt", "passport", "unrecognized"
    new_type: str = Form(...),  # "receipt", "passport", "delete"
    passport_name: str = Form(None),  # 여권의 경우 이름도 함께 전달
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """항목의 유형을 변경합니다 (영수증 ↔ 여권 ↔ 삭제)"""
    try:
        # 현재 항목 조회
        current_item = None
        if current_type == "receipt":
            # 롯데 영수증 확인
            current_item = db.query(Receipt).filter(
                Receipt.id == item_id,
                Receipt.user_id == current_user.id
            ).first()
            
            # 신라 영수증 확인
            if not current_item:
                current_item = db.query(ShillaReceipt).filter(
                    ShillaReceipt.id == item_id,
                    ShillaReceipt.user_id == current_user.id
                ).first()
                current_type = "shilla_receipt"
                
        elif current_type == "passport":
            # 먼저 ID로 검색
            current_item = db.query(Passport).filter(
                Passport.id == item_id,
                Passport.user_id == current_user.id
            ).first()
            
            # ID로 찾지 못했다면 이름으로 검색
            if not current_item and passport_name:
                current_item = db.query(Passport).filter(
                    Passport.name == passport_name,
                    Passport.user_id == current_user.id
                ).first()
            
        elif current_type == "unrecognized":
            current_item = db.query(UnrecognizedImage).filter(
                UnrecognizedImage.id == item_id,
                UnrecognizedImage.user_id == current_user.id
            ).first()
        
        if not current_item:
            return JSONResponse(content={"success": False, "message": "항목을 찾을 수 없습니다."}, status_code=404)
        
        file_path = current_item.file_path
        upload_id = getattr(current_item, 'upload_id', None)
        
        # 삭제 처리
        if new_type == "delete":
            db.delete(current_item)
            
            # 관련 매칭 로그도 삭제 (영수증인 경우)
            if current_type in ["receipt", "shilla_receipt"]:
                if hasattr(current_item, 'receipt_number') and current_item.receipt_number:
                    db.query(ReceiptMatchLog).filter(
                        ReceiptMatchLog.receipt_number == current_item.receipt_number,
                        ReceiptMatchLog.user_id == current_user.id
                    ).delete()
            
            db.commit()
            return JSONResponse(content={"success": True, "message": "항목이 삭제되었습니다."})
        
        # 타입 변경 처리
        if new_type == "receipt":
            # 면세점 타입 확인
            duty_free_type = "lotte"  # 기본값
            shilla_count = db.execute(sql_text("SELECT COUNT(*) FROM shilla_receipts WHERE user_id = :user_id"), 
                                     {"user_id": current_user.id}).scalar()
            if shilla_count > 0:
                duty_free_type = "shilla"
            
            if duty_free_type == "shilla":
                new_item = ShillaReceipt(
                    user_id=current_user.id,
                    upload_id=upload_id,
                    file_path=file_path,
                    receipt_number=None,
                    passport_number=None
                )
            else:
                new_item = Receipt(
                    user_id=current_user.id,
                    upload_id=upload_id,
                    file_path=file_path,
                    receipt_number=None
                )
            
            db.add(new_item)
            
            # 롯데 면세점의 경우, receipt_number가 None인 영수증은 자동으로 매칭되지 않은 것으로 처리됨
            # (매칭 로그는 영수증 번호가 입력될 때 생성됨)
            
        elif new_type == "passport":
            new_item = Passport(
                user_id=current_user.id,
                upload_id=upload_id,
                file_path=file_path,
                passport_number=None,
                birthday=None,
                name=None,
                is_matched=False
            )
            db.add(new_item)
            
        elif new_type == "unrecognized":
            new_item = UnrecognizedImage(
                user_id=current_user.id,
                upload_id=upload_id,
                file_path=file_path
            )
            db.add(new_item)
        
        # 기존 항목 삭제
        db.delete(current_item)
        
        # 관련 매칭 로그 정리 (영수증인 경우)
        if current_type in ["receipt", "shilla_receipt"]:
            if hasattr(current_item, 'receipt_number') and current_item.receipt_number:
                db.query(ReceiptMatchLog).filter(
                    ReceiptMatchLog.receipt_number == current_item.receipt_number,
                    ReceiptMatchLog.user_id == current_user.id
                ).delete()
        
        db.commit()
        
        type_names = {
            "receipt": "영수증",
            "passport": "여권", 
            "unrecognized": "인식안된 이미지"
        }
        
        return JSONResponse(content={
            "success": True, 
            "message": f"항목이 {type_names.get(new_type, new_type)}(으)로 변경되었습니다.",
            "new_id": new_item.id if new_type != "delete" else None
        })
        
    except Exception as e:
        db.rollback()
        print(f"유형 변경 오류: {str(e)}")
        return JSONResponse(content={"success": False, "message": f"유형 변경 중 오류가 발생했습니다: {str(e)}"}, status_code=500)

@router.get("/api/unrecognized-images/")
async def get_unrecognized_images(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """인식되지 않은 이미지 목록을 반환"""
    try:
        unrecognized_images = db.query(UnrecognizedImage).filter(
            UnrecognizedImage.user_id == current_user.id
        ).order_by(UnrecognizedImage.created_at.desc()).all()
        
        images = []
        for img in unrecognized_images:
            images.append({
                "id": img.id,
                "file_path": img.file_path,
                "created_at": img.created_at.isoformat() if img.created_at else None
            })
        
        return {
            "images": images,
            "total_count": len(images)
        }
        
    except Exception as e:
        print(f"인식되지 않은 이미지 조회 오류: {str(e)}")
        return {"error": str(e)}

@router.post("/api/delete-all-unrecognized/")
async def delete_all_unrecognized_images(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """모든 인식되지 않은 이미지를 삭제합니다"""
    try:
        # 현재 사용자의 인식되지 않은 이미지 조회
        unrecognized_images = db.query(UnrecognizedImage).filter(
            UnrecognizedImage.user_id == current_user.id
        ).all()
        
        deleted_count = len(unrecognized_images)
        
        if deleted_count == 0:
            return {"success": True, "deleted_count": 0, "message": "삭제할 이미지가 없습니다."}
        
        # 모든 이미지 삭제
        db.query(UnrecognizedImage).filter(
            UnrecognizedImage.user_id == current_user.id
        ).delete()
        
        db.commit()
        
        return {
            "success": True, 
            "deleted_count": deleted_count,
            "message": f"{deleted_count}개의 인식되지 않은 이미지가 삭제되었습니다."
        }
        
    except Exception as e:
        db.rollback()
        print(f"전체 삭제 오류: {str(e)}")
        return {"success": False, "message": f"전체 삭제 중 오류가 발생했습니다: {str(e)}"}

@router.get("/unrecognized-images/")
async def unrecognized_images_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """인식되지 않은 이미지 관리 페이지"""
    return templates.TemplateResponse(
        "unrecognized_images.html",
        {
            "request": request,
            "user": current_user
        }
    )

@router.post("/api/update-customer-names/")
async def update_customer_names_to_passport_names(
    current_user: User = Depends(get_current_user)
):
    """기존 저장된 데이터의 고객명을 여권 풀네임으로 업데이트"""
    try:
        receipt_service = ReceiptService()
        result = receipt_service.update_excel_names_to_passport_names(current_user.id)
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "details": {
                    "updated_receipt_logs": result["updated_receipt_logs"],
                    "updated_history": result["updated_history"]
                }
            }
        else:
            return {
                "success": False,
                "error": result["error"]
            }
            
    except Exception as e:
        print(f"고객명 업데이트 API 오류: {e}")
        return {
            "success": False,
            "error": str(e)
        }
