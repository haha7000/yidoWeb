from app.models.models import Passport, Receipt
from app.core.database import my_engine, SessionLocal
from datetime import datetime

def OcrToDb(ocr_data, image_path):
    batch = []

    with SessionLocal() as db:
        new_result = Passport(
            file_path=image_path,
            passport_number=ocr_data.get("passportNumber"),
            birthday=datetime.strptime(ocr_data["birthday"], "%d %b %Y").date() if ocr_data.get("birthday") else None,
            name=ocr_data.get("name"),
            matched=False
        )
        db.add(new_result)
        db.commit()
        db.refresh(new_result)

        receipt_list = ocr_data.get("receiptNumber")
        if receipt_list:
            for receipt in receipt_list:
                new_receipt = Receipt(
                    file_path=image_path,
                    receipt_number=receipt,
                    matched=False
                )
                db.add(new_receipt)
        else:
            new_receipt = Receipt(
                file_path=image_path,
                receipt_number=None,
                matched=False
            )
            db.add(new_receipt)
            print(f"경고: {image_path}에서 영수증 번호를 찾을 수 없습니다. (나중에 수정 가능)")
        
        db.commit()
        print(f"DB 저장 완료 - 이미지: {image_path}")
