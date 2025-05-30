from app.models.models import ShillaReceipt, ReceiptMatchLog, Passport
from app.core.database import SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy import text


def shilla_matching_result(user_id):
    """
    신라 면세점 전용 매칭 로직
    1. ShillaReceipt.receiptNumber를 shilla_excel_data.receiptNumber와 매칭
    2. 매칭된 경우 shilla_excel_data에 passportNumber 업데이트
    3. shilla_excel_data.passportNumber를 passports.passport_number와 매칭하여 이름과 생일 가져오기
    """
    with SessionLocal() as session:
        # 1단계: 영수증 번호 매칭 및 여권번호 업데이트
        sql_update_passport = """
        UPDATE shilla_excel_data se
        SET passport_number = sr.passport_number
        FROM shilla_receipts sr
        WHERE se."receiptNumber"::text = sr.receipt_number  -- 숫자를 문자열로 변환
        AND sr.user_id = :user_id
        AND sr.passport_number IS NOT NULL
        """
        updated_rows = session.execute(text(sql_update_passport), {"user_id": user_id}).rowcount
        print(f"신라 엑셀 데이터에 여권번호 업데이트: {updated_rows}행")
        
        # 2단계: 영수증 매칭 결과 로그 저장
        sql_matching = """
        SELECT DISTINCT sr.receipt_number,
               CASE
                   WHEN se."receiptNumber" IS NOT NULL THEN TRUE
                   ELSE FALSE 
               END AS is_matched,
               se.name as excel_name,
               sr.passport_number
        FROM shilla_receipts sr
        LEFT JOIN shilla_excel_data se
          ON se."receiptNumber"::text = sr.receipt_number
        WHERE sr.user_id = :user_id
        """
        
        results = session.execute(text(sql_matching), {"user_id": user_id}).fetchall()
        print(f"매칭 결과: {len(results)}개")
        
        for row in results:
            receipt_number, is_matched, excel_name, passport_number = row
            
            # 여권 정보 조회 (passport_number로 매칭)
            passport_info = None
            if passport_number:
                passport = session.query(Passport).filter(
                    Passport.passport_number == passport_number,
                    Passport.user_id == user_id
                ).first()
                
                if passport:
                    passport_info = {
                        'name': passport.name,
                        'birthday': passport.birthday
                    }
                    print(f"여권 정보 찾음: {passport.name}, {passport.birthday}")
            
            # 매칭 로그 저장
            match_log = ReceiptMatchLog(
                user_id=user_id,
                receipt_number=receipt_number,
                is_matched=is_matched,
                excel_name=excel_name if is_matched else None,
                passport_number=passport_number,
                birthday=passport_info['birthday'] if passport_info else None
            )
            session.add(match_log)
            print(f"매칭 로그 저장: {receipt_number}, 매칭됨={is_matched}, 고객명={excel_name}")

        session.commit()
        print("신라 매칭 결과 저장 완료")


def fetch_shilla_results(user_id):
    """
    신라 면세점 결과 조회 - 컬럼명 수정
    """
    with SessionLocal() as db:
        # 매칭된 영수증 정보 조회 - 타입 캐스팅 추가
        matched_sql = """
        SELECT DISTINCT 
            sr.receipt_number,
            se.name as excel_name,
            sr.passport_number,
            p.name as passport_name,
            p.birthday
        FROM shilla_receipts sr
        JOIN shilla_excel_data se ON se."receiptNumber"::text = sr.receipt_number  -- 수정
        LEFT JOIN passports p ON sr.passport_number = p.passport_number AND p.user_id = :user_id
        WHERE sr.user_id = :user_id
        """
        matched = db.execute(text(matched_sql), {"user_id": user_id}).fetchall()
        
        # 매칭되지 않은 영수증 조회 - 타입 캐스팅 추가
        unmatched_sql = """
        SELECT DISTINCT sr.*
        FROM shilla_receipts sr
        LEFT JOIN shilla_excel_data se ON se."receiptNumber"::text = sr.receipt_number  -- 수정
        WHERE se."receiptNumber" IS NULL AND sr.user_id = :user_id
        """
        unmatched = db.execute(text(unmatched_sql), {"user_id": user_id}).fetchall()
        
        # 매칭된 결과를 고객별로 그룹화
        customer_data = {}
        for row in matched:
            receipt_number, excel_name, passport_number, passport_name, birthday = row
            
            if excel_name not in customer_data:
                customer_data[excel_name] = {
                    'name': excel_name,
                    'receipt_numbers': [],
                    'passport_number': passport_number,
                    'passport_name': passport_name,
                    'birthday': birthday,
                    'needs_update': passport_name is None or passport_name != excel_name
                }
            customer_data[excel_name]['receipt_numbers'].append(receipt_number)
        
        matched_list = list(customer_data.values())
        
        return matched_list, unmatched