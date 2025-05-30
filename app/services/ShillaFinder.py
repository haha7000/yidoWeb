from app.services.ShillaGptResponse import ShillaClassificationUseGpt
from app.services.ocr_module import VisionOcr
from app.models.models import ShillaReceipt, Passport, UnrecognizedImage
from app.core.database import SessionLocal
import json

def ShillaAiOcr(imagePath, user_id):
    db = SessionLocal()
    try:
        # OCR 및 GPT 처리
        ocrResult = VisionOcr(imagePath)
        result = ShillaClassificationUseGpt(ocrResult)

        # JSON 문자열을 파싱
        parsed_result = json.loads(result)
        print(f"파싱된 결과: {imagePath}")
        print(json.dumps(parsed_result, indent=2, ensure_ascii=False))

        # 데이터 저장 여부 확인
        saved_data = False

        # 영수증 처리 (신라용)
        if "receipts" in parsed_result and parsed_result["receipts"]:
            for receipt in parsed_result["receipts"]:
                receiptNumber = receipt.get('receiptNumber', '')
                passportNumber = receipt.get('passportNumber', '')  # 신라는 영수증에서 여권번호 추출
                
                if receiptNumber:  # 빈 문자열이 아닌 경우만 추가
                    new_receipt = ShillaReceipt(
                        user_id=user_id,
                        receipt_number=str(receiptNumber),  # 문자열로 명시적 변환
                        passport_number=passportNumber if passportNumber else None,
                        file_path=imagePath
                    )
                    db.add(new_receipt)
                    saved_data = True
                    print(f"신라 영수증 저장: {receiptNumber}, 여권번호: {passportNumber}")

        # 여권 처리 (기존과 동일)
        if "passports" in parsed_result and parsed_result["passports"]:
            for passport in parsed_result["passports"]:
                PassportName = passport.get('name', '')
                PassportNumber = passport.get('passportNumber', '')
                PassportBirthday = passport.get('birthDay', '')

                if PassportName or PassportNumber:  # 최소한 이름이나 여권번호가 있는 경우
                    new_passport = Passport(
                        user_id=user_id,
                        file_path=imagePath,
                        name=PassportName if PassportName else None,
                        birthday=PassportBirthday if PassportBirthday else None,
                        passport_number=PassportNumber if PassportNumber else None
                    )
                    db.add(new_passport)
                    saved_data = True
                    print(f"여권 저장: {PassportName}, 번호: {PassportNumber}")

        if not saved_data:
            # 인식된 데이터가 없는 경우 인식되지 않은 이미지로 저장
            print(f"인식된 데이터가 없어서 unrecognized_images에 저장: {imagePath}")
            unrecognized = UnrecognizedImage(
                user_id=user_id,
                file_path=imagePath
            )
            db.add(unrecognized)

        # 변경사항 저장
        db.commit()
        print(f"데이터베이스 커밋 완료: {imagePath}")
        return True

    except json.JSONDecodeError as e:
        # JSON 파싱 오류
        db.rollback()
        print(f"JSON 파싱 오류: {str(e)}")
        print(f"GPT 응답: {result}")
        
        # 인식되지 않은 이미지로 저장
        unrecognized = UnrecognizedImage(
            user_id=user_id,
            file_path=imagePath
        )
        db.add(unrecognized)
        db.commit()
        return False

    except Exception as e:
        # 기타 오류 발생 시 롤백
        db.rollback()
        print(f"오류 발생: {str(e)}")
        
        # 인식되지 않은 이미지로 저장
        try:
            unrecognized = UnrecognizedImage(
                user_id=user_id,
                file_path=imagePath
            )
            db.add(unrecognized)
            db.commit()
        except Exception as save_error:
            print(f"unrecognized_images 저장 실패: {str(save_error)}")
        
        return False

    finally:
        # 세션 종료
        db.close()