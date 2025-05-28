from gpt import classificationUseGpt
from OcrOnlyTest import VisionOcr
from app.models.models import Receipt, Passport, UnrecognizedImage
from app.core.database import SessionLocal
import json

def AiOcr(imagePath):
    db = SessionLocal()
    try:
        # OCR 및 GPT 처리
        ocrResult = VisionOcr(imagePath)
        with open("/Users/gimdonghun/Downloads/ocr.txt", "w") as f:
            f.write(ocrResult)
        result = classificationUseGpt(ocrResult)

        # JSON 문자열을 파싱
        parsed_result = json.loads(result)
        print(f"파싱된 결과: {imagePath}")
        print(json.dumps(parsed_result, indent=2, ensure_ascii=False))

        # 영수증 처리
        receipt_numbers = []
        if "receipts" in parsed_result:
            for receipt in parsed_result["receipts"]:
                receiptNumber = receipt.get('receiptNumber', '')
                if receiptNumber:  # 빈 문자열이 아닌 경우만 추가
                    receipt_numbers.append(receiptNumber)
            
            for receiptNumber in receipt_numbers:
                new_receipt = Receipt(
                    receipt_number=receiptNumber,
                    file_path=imagePath
                )
                db.add(new_receipt)

        # 여권 처리
        if "passports" in parsed_result:
            for passport in parsed_result["passports"]:
                PassportName = passport.get('name', '')
                PassportNumber = passport.get('passportNumber', '')
                PassportBirthday = passport.get('birthDay', '')

                new_passport = Passport(
                    file_path=imagePath,
                    name=PassportName,
                    birthday=PassportBirthday,
                    passport_number=PassportNumber
                )
                db.add(new_passport)

        # 변경사항 저장
        db.commit()
        return True

    except Exception as e:
        # 오류 발생 시 롤백
        db.rollback()
        print(f"오류 발생: {str(e)}")
        return False

    finally:
        # 세션 종료
        db.close()

# 사용 예시
imagePath = "/Users/gimdonghun/Downloads/i20.png"
success = AiOcr(imagePath)
if success:
    print("처리가 성공적으로 완료되었습니다.")
else:
    print("처리 중 오류가 발생했습니다.")