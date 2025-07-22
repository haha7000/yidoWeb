from app.services.ShillaGptResponse import ShillaClassificationUseGpt
from app.services.ocr_module import VisionOcr
from app.models.models import ShillaReceipt, Passport, UnrecognizedImage
from app.core.database import SessionLocal
import json
import requests
from datetime import datetime

def parse_and_validate_date(date_string):
    """
    GPT API에서 반환된 날짜 문자열을 파싱하고 검증
    형식: "DD MMM YYYY" (예: "09 Jun 1994")
    """
    if not date_string or not date_string.strip():
        return None
    
    try:
        # 공백으로 분리
        parts = date_string.strip().split()
        if len(parts) != 3:
            print(f"날짜 형식 오류 - 잘못된 구조: {date_string}")
            return None
            
        day_str, month_str, year_str = parts
        
        # 날짜 검증
        try:
            day = int(day_str)
            if day < 1 or day > 31:
                print(f"날짜 형식 오류 - 잘못된 일: {day}")
                return None
        except ValueError:
            print(f"날짜 형식 오류 - 일이 숫자가 아님: {day_str}")
            return None
        
        # 월 검증
        valid_months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        if month_str not in valid_months:
            print(f"날짜 형식 오류 - 잘못된 월: {month_str}")
            return None
        
        # 연도 검증
        try:
            year = int(year_str)
            if year < 1900 or year > 2024:  # 합리적인 연도 범위
                print(f"날짜 형식 오류 - 잘못된 연도: {year}")
                return None
        except ValueError:
            print(f"날짜 형식 오류 - 연도가 숫자가 아님: {year_str}")
            return None
        
        # datetime으로 파싱 시도
        parsed_date = datetime.strptime(date_string, '%d %b %Y').date()
        print(f"날짜 파싱 성공: {date_string} -> {parsed_date}")
        return parsed_date
        
    except ValueError as e:
        print(f"날짜 파싱 오류: {date_string} - {e}")
        return None
    except Exception as e:
        print(f"예상치 못한 날짜 파싱 오류: {date_string} - {e}")
        return None

def ShillaAiOcr(imagePath, user_id):
    db = SessionLocal()
    try:
        # response = requests.post("http://localhost:9000/ocr", files={"file": open(imagePath, "rb")})
        # ocrResult = response.json()
        # ocrResult = ocrResult['text']
        ocrResult = VisionOcr(imagePath)
        result = ShillaClassificationUseGpt(ocrResult)

        # JSON 문자열을 파싱
        parsed_result = json.loads(result)
        print(f"파싱된 결과: {imagePath}")
        print(json.dumps(parsed_result, indent=2, ensure_ascii=False))

        saved_data = False

        # 영수증 처리 (여권번호 포함)
        if "receipts" in parsed_result and parsed_result["receipts"]:
            for receipt in parsed_result["receipts"]:
                receiptNumber = receipt.get('receiptNumber', '')
                passportNumber = receipt.get('passportNumber', '')  # 여권번호도 추출
                if receiptNumber:  # 빈 문자열이 아닌 경우만 추가
                    new_receipt = ShillaReceipt(
                        user_id=user_id,
                        receipt_number=receiptNumber,
                        passport_number=passportNumber if passportNumber else None,  # 여권번호 저장
                        file_path=imagePath
                    )
                    db.add(new_receipt)
                    saved_data = True
                    print(f"신라 영수증 저장: {receiptNumber}, 여권번호: {passportNumber if passportNumber else '없음'}")

        # 여권 처리 (날짜 검증 추가)
        if "passports" in parsed_result and parsed_result["passports"]:
            for passport in parsed_result["passports"]:
                PassportName = passport.get('name', '')
                PassportNumber = passport.get('passportNumber', '')
                PassportBirthday = passport.get('birthDay', '')

                # 날짜 파싱 및 검증
                parsed_birthday = None
                if PassportBirthday and PassportBirthday.strip():
                    parsed_birthday = parse_and_validate_date(PassportBirthday)
                    if parsed_birthday is None:
                        print(f"잘못된 날짜 형식으로 인해 생일을 None으로 설정: {PassportBirthday}")

                if PassportName or PassportNumber:  # 최소한 이름이나 여권번호가 있는 경우
                    new_passport = Passport(
                        user_id=user_id,
                        file_path=imagePath,
                        name=PassportName if PassportName else None,
                        birthday=parsed_birthday,  # 검증된 날짜 또는 None
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
        # 기타 오류
        db.rollback()
        print(f"오류 발생: {str(e)}")
        
        # 인식되지 않은 이미지로 저장
        unrecognized = UnrecognizedImage(
        user_id=user_id,
        file_path=imagePath
        )
        db.add(unrecognized)
        db.commit()
        return False

    finally:
        db.close()