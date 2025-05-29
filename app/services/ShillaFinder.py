from app.services.ShillaGptResponse import ShillaClassificationUseGpt
from app.services.ocr_module import VisionOcr
from app.models.models import Receipt, Passport, UnrecognizedImage
from app.core.database import SessionLocal
import json

def ShillaAiOcr(imagePath, user_id):
    db = SessionLocal()
    # OCR 및 GPT 처리
    ocrResult = VisionOcr(imagePath)
    result = ShillaClassificationUseGpt(ocrResult)

    # JSON 문자열을 파싱
    parsed_result = json.loads(result)
    
    # 첫 번째 항목에서 receiptNumber와 passportNumber 추출
    if parsed_result and len(parsed_result) > 0:
        receipt_number = parsed_result[0].get('receiptNumber')
        passport_number = parsed_result[0].get('passportNumber')
        
        
        return receipt_number, passport_number
    
    return None, None



# 테스트 코드
receipt_num, passport_num = ShillaAiOcr("/Users/gimdonghun/Downloads/Shilla/Shilla7.jpg", 1)

print(receipt_num, passport_num)