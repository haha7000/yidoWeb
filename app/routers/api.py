"""
API 관련 라우터 - AJAX 및 데이터 조회용 API들
"""
from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.models import (
    User, Passport, Receipt, ShillaReceipt, ReceiptMatchLog, 
    UnrecognizedImage
)
from app.core.auth import get_current_user, get_db
from app.core.database import SessionLocal
from app.services.passportMatching import get_unmatched_passports

router = APIRouter(prefix="/api", tags=["API"])

@router.get("/available-passports/")
async def get_available_passports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """매칭 가능한 여권 목록을 JSON으로 반환"""
    try:
        # 신라와 롯데 모두에서 매칭되지 않은 여권들 조회
        sql = text("""
            SELECT DISTINCT p.name, p.passport_number, p.birthday
            FROM passports p
            WHERE p.user_id = :user_id
            AND p.is_matched = FALSE
            ORDER BY p.name
        """)
        
        results = db.execute(sql, {"user_id": current_user.id}).fetchall()
        
        passports = []
        for row in results:
            passports.append({
                "name": row[0],
                "passport_number": row[1],
                "birthday": row[2].strftime('%Y-%m-%d') if row[2] else None
            })
        
        return {"passports": passports}
        
    except Exception as e:
        print(f"매칭 가능한 여권 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="여권 목록을 가져올 수 없습니다.")

@router.post("/calculate-commission")
async def calculate_commission_api(current_user: User = Depends(get_current_user)):
    """할인율과 수수료를 계산하여 데이터베이스에 저장"""
    try:
        from app.services.commission_service import calculate_discounts_and_commissions
        
        # 현재 사용자의 데이터만 계산
        result = calculate_discounts_and_commissions(user_id=current_user.id)
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "data": {
                    "processed_count": result["processed_count"],
                    "error_count": result.get("error_count", 0),
                    "total_records": result.get("total_records", 0)
                }
            }
        else:
            raise HTTPException(status_code=500, detail=result["message"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"할인율 및 수수료 계산 중 오류가 발생했습니다: {str(e)}")

@router.get("/commission-summary")
async def get_commission_summary_api(current_user: User = Depends(get_current_user)):
    """수수료 계산 결과 요약 조회"""
    try:
        from app.services.commission_service import get_commission_summary
        
        # 현재 사용자의 데이터 요약
        result = get_commission_summary(user_id=current_user.id)
        
        if result["success"]:
            return {
                "success": True,
                "data": result["summary"]
            }
        else:
            raise HTTPException(status_code=500, detail=result["message"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"수수료 요약 조회 중 오류가 발생했습니다: {str(e)}")

@router.get("/commission-details")
async def get_commission_details_api(current_user: User = Depends(get_current_user)):
    """할인율과 수수료가 계산된 상세 데이터 조회"""
    try:
        db = SessionLocal()
        
        # 매칭된 데이터 중 할인율 또는 수수료가 계산된 데이터 조회
        query = text("""
            SELECT 
                id, receipt_number, excel_name, sales_date, category, brand, 
                product_code, discount_amount_krw, sales_price_usd, net_sales_krw, 
                store_branch, discount_rate, commission_fee
            FROM receipt_match_log 
            WHERE user_id = :user_id 
            AND is_matched = TRUE
            AND (discount_rate IS NOT NULL OR commission_fee IS NOT NULL)
            ORDER BY sales_date DESC, receipt_number
        """)
        
        results = db.execute(query, {"user_id": current_user.id}).fetchall()
        db.close()
        
        # 결과를 JSON 형태로 변환
        details = []
        for row in results:
            details.append({
                "id": row.id,
                "receipt_number": row.receipt_number,
                "excel_name": row.excel_name,
                "sales_date": row.sales_date.isoformat() if row.sales_date else None,
                "category": row.category,
                "brand": row.brand,
                "product_code": row.product_code,
                "discount_amount_krw": float(row.discount_amount_krw) if row.discount_amount_krw else None,
                "sales_price_usd": float(row.sales_price_usd) if row.sales_price_usd else None,
                "net_sales_krw": float(row.net_sales_krw) if row.net_sales_krw else None,
                "store_branch": row.store_branch,
                "discount_rate": float(row.discount_rate) if row.discount_rate else None,
                "commission_fee": float(row.commission_fee) if row.commission_fee else None
            })
        
        return {
            "success": True,
            "data": details,
            "total_count": len(details)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"수수료 상세 조회 중 오류가 발생했습니다: {str(e)}")

@router.get("/next-unmatched-passport-by-id/")
async def get_next_unmatched_passport_by_id(
    current_id: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """ID 기반으로 다음 매칭되지 않은 여권 조회"""
    try:
        unmatched_passports = get_unmatched_passports(current_user.id)
        
        if not unmatched_passports:
            return {
                "success": True,
                "has_more": False,
                "next_passport": None,
                "message": "매칭되지 않은 여권이 없습니다."
            }
        
        # 현재 여권의 다음 여권 찾기
        next_passport = None
        current_found = False
        
        for passport_item in unmatched_passports:
            if current_found:
                next_passport = passport_item
                break
            if passport_item.get('id') == current_id:
                current_found = True
        
        if next_passport:
            return {
                "success": True,
                "has_more": True,
                "next_passport": {
                    "id": next_passport['id'],
                    "name": next_passport['passport_name']
                },
                "message": f"다음 여권: {next_passport['passport_name']}"
            }
        else:
            return {
                "success": True,
                "has_more": False,
                "next_passport": None,
                "message": "더 이상 처리할 여권이 없습니다."
            }
            
    except Exception as e:
        print(f"다음 여권 조회 오류: {e}")
        return {
            "success": False,
            "error": str(e),
            "has_more": False,
            "next_passport": None
        }

@router.get("/next-unmatched-passport/")
async def get_next_unmatched_passport(
    current_name: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """다음 매칭되지 않은 여권을 반환"""
    try:
        unmatched_passports = get_unmatched_passports(current_user.id)
        
        if not unmatched_passports:
            return {"next_passport": None, "has_more": False, "remaining_count": 0}
        
        # 현재 여권의 인덱스 찾기
        current_index = -1
        for i, passport in enumerate(unmatched_passports):
            passport_name = passport.get("passport_name") if isinstance(passport, dict) else passport.name
            if passport_name == current_name:
                current_index = i
                break
        
        next_index = current_index + 1
        if next_index < len(unmatched_passports):
            next_passport = unmatched_passports[next_index]
            
            # 딕셔너리인지 객체인지 확인
            if isinstance(next_passport, dict):
                return {
                    "next_passport": {
                        "name": next_passport.get("passport_name"),
                        "passport_number": next_passport.get("passport_number"),
                        "birthday": next_passport.get("birthday").strftime('%Y-%m-%d') if next_passport.get("birthday") else None,
                        "file_path": next_passport.get("file_path")
                    },
                    "has_more": True,
                    "remaining_count": len(unmatched_passports) - next_index
                }
            else:
                return {
                    "next_passport": {
                        "name": next_passport.name,
                        "passport_number": next_passport.passport_number,
                        "birthday": next_passport.birthday.strftime('%Y-%m-%d') if next_passport.birthday else None,
                        "file_path": next_passport.file_path
                    },
                    "has_more": True,
                    "remaining_count": len(unmatched_passports) - next_index
                }
        else:
            return {"next_passport": None, "has_more": False, "remaining_count": 0}
            
    except Exception as e:
        print(f"다음 매칭되지 않은 여권 조회 오류: {str(e)}")
        return {"error": str(e), "next_passport": None, "has_more": False}

@router.get("/next-unmatched-receipt/")
async def get_next_unmatched_receipt(
    current_id: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """현재 영수증 다음의 매칭되지 않은 영수증을 반환"""
    try:
        # 사용자의 면세점 타입 확인
        duty_free_type = "lotte"  # 기본값
        
        # 신라 데이터가 있는지 확인
        shilla_count = db.execute(text("SELECT COUNT(*) FROM shilla_receipts WHERE user_id = :user_id"), 
                                 {"user_id": current_user.id}).scalar()
        if shilla_count > 0:
            duty_free_type = "shilla"
        
        if duty_free_type == "shilla":
            # 신라 면세점: 매칭되지 않은 영수증 조회
            unmatched_sql = text("""
                SELECT sr.id, sr.receipt_number, sr.passport_number, sr.file_path
                FROM shilla_receipts sr
                LEFT JOIN shilla_excel_data se ON sr.receipt_number = se."receiptNumber"::text
                WHERE sr.user_id = :user_id
                AND se."receiptNumber" IS NULL
                AND sr.id > :current_id
                ORDER BY sr.id
                LIMIT 1
            """)
        else:
            # 롯데 면세점: 매칭되지 않은 영수증 조회
            unmatched_sql = text("""
                SELECT r.id, r.receipt_number, NULL as passport_number, r.file_path
                FROM receipts r
                JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number
                WHERE rml.is_matched = FALSE 
                AND r.user_id = :user_id 
                AND rml.user_id = :user_id
                AND r.id > :current_id
                ORDER BY r.id
                LIMIT 1
            """)
        
        result = db.execute(unmatched_sql, {"user_id": current_user.id, "current_id": current_id}).fetchone()
        
        if result:
            return {
                "next_receipt": {
                    "id": result.id,
                    "receipt_number": result.receipt_number,
                    "passport_number": result.passport_number if hasattr(result, 'passport_number') else None,
                    "file_path": result.file_path
                },
                "has_more": True
            }
        else:
            return {"next_receipt": None, "has_more": False}
            
    except Exception as e:
        print(f"다음 매칭되지 않은 영수증 조회 오류: {str(e)}")
        return {"error": str(e), "next_receipt": None, "has_more": False}

@router.get("/unmatched-receipts/")
async def get_unmatched_receipts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """매칭되지 않은 영수증 목록을 반환"""
    try:
        # 사용자의 면세점 타입 확인
        duty_free_type = "lotte"  # 기본값
        
        # 신라 데이터가 있는지 확인
        shilla_count = db.execute(text("SELECT COUNT(*) FROM shilla_receipts WHERE user_id = :user_id"), 
                                 {"user_id": current_user.id}).scalar()
        if shilla_count > 0:
            duty_free_type = "shilla"
        
        if duty_free_type == "shilla":
            # 신라 면세점: 매칭되지 않은 영수증 조회
            unmatched_sql = text("""
                SELECT sr.id, sr.receipt_number, sr.passport_number, sr.file_path
                FROM shilla_receipts sr
                LEFT JOIN shilla_excel_data se ON sr.receipt_number = se."receiptNumber"::text
                WHERE sr.user_id = :user_id
                AND se."receiptNumber" IS NULL
                ORDER BY sr.id
            """)
        else:
            # 롯데 면세점: 매칭되지 않은 영수증 조회
            unmatched_sql = text("""
                SELECT r.id, r.receipt_number, NULL as passport_number, r.file_path
                FROM receipts r
                JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number
                WHERE rml.is_matched = FALSE 
                AND r.user_id = :user_id 
                AND rml.user_id = :user_id
                ORDER BY r.id
            """)
        
        results = db.execute(unmatched_sql, {"user_id": current_user.id}).fetchall()
        
        receipts = []
        for row in results:
            receipts.append({
                "id": row.id,
                "receipt_number": row.receipt_number,
                "passport_number": row.passport_number if hasattr(row, 'passport_number') else None,
                "file_path": row.file_path
            })
        
        return {
            "receipts": receipts,
            "total_count": len(receipts),
            "duty_free_type": duty_free_type
        }
        
    except Exception as e:
        print(f"매칭되지 않은 영수증 조회 오류: {str(e)}")
        return {"error": str(e)}

@router.post("/change-type/")
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
            shilla_count = db.execute(text("SELECT COUNT(*) FROM shilla_receipts WHERE user_id = :user_id"), 
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

@router.get("/unrecognized-images/")
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

@router.post("/delete-all-unrecognized/")
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

@router.post("/unmatch-passport/{passport_id}")
async def unmatch_passport(
    passport_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """여권 매칭을 해제하는 API"""
    try:
        # 여권 조회
        passport = db.query(Passport).filter(
            Passport.id == passport_id,
            Passport.user_id == current_user.id
        ).first()
        
        if not passport:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "여권을 찾을 수 없습니다."}
            )
        
        # 매칭 상태를 False로 변경
        passport.is_matched = False
        
        # 관련 receipt_match_log 업데이트 (롯데)
        if passport.passport_number:
            db.execute(text("""
                UPDATE receipt_match_log 
                SET is_matched = FALSE 
                WHERE passport_number = :passport_number 
                AND user_id = :user_id
            """), {
                "passport_number": passport.passport_number,
                "user_id": current_user.id
            })
        
        db.commit()
        
        return JSONResponse(content={
            "success": True,
            "message": f"'{passport.name}' 여권의 매칭이 해제되었습니다."
        })
        
    except Exception as e:
        db.rollback()
        print(f"매칭 해제 오류: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"매칭 해제 중 오류가 발생했습니다: {str(e)}"}
        )