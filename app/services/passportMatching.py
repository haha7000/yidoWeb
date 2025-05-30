from app.models.models import Receipt, ReceiptMatchLog, Passport, User, DutyFreeType
from app.core.database import SessionLocal
from sqlalchemy import text


def fetch_results(user_id):
    with SessionLocal() as db:
        # 사용자 조회하여 면세점 타입 확인
        user = db.query(User).filter(User.id == user_id).first()
        
        if user.duty_free_type == DutyFreeType.LOTTE:
            # 사용자별 매칭된 영수증 번호와 이름 조회 (롯데) - 컬럼명 수정
            sql = """
            SELECT r.receipt_number, e.name
            FROM receipts r
            JOIN receipt_match_log m ON r.receipt_number = m.receipt_number
            JOIN lotte_excel_data e ON r.receipt_number = e."receiptNumber"
            WHERE m.is_matched = TRUE AND r.user_id = :user_id AND m.user_id = :user_id;
            """
            matched = db.execute(text(sql), {"user_id": user_id}).fetchall()

            # 사용자별 매칭되지 않은 영수증 번호 조회
            unmatched_sql = """
            SELECT r.*
            FROM receipts r
            JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number
            WHERE rml.is_matched = FALSE AND r.user_id = :user_id AND rml.user_id = :user_id
            """
            unmatched = db.execute(text(unmatched_sql), {"user_id": user_id}).fetchall()
        else:
            # 신라 면세점인 경우 shilla_matching 모듈 사용
            from app.services.shilla_matching import fetch_shilla_results
            return fetch_shilla_results(user_id)

        return matched, unmatched
    

def matching_passport(user_id):
    # 사용자 조회하여 면세점 타입 확인
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        
        if user.duty_free_type == DutyFreeType.SHILLA:
            # 신라 면세점용 처리
            from app.services.shilla_matching import fetch_shilla_results
            matched_list, unmatched = fetch_shilla_results(user_id)
            
            print(f"사용자 {user_id}의 신라 matched 정보: {matched_list}")
            print("=== 신라 매칭된 영수증과 여권 정보 ===")
            
            # matched_list를 passport_info 형태로 변환
            passport_info = []
            for customer in matched_list:
                info = {
                    "name": customer['name'],
                    "receipt_numbers": customer['receipt_numbers'],
                    "passport_number": customer.get('passport_number'),
                    "birthday": customer.get('birthday'),
                    "needs_update": customer.get('needs_update', False)
                }
                passport_info.append(info)
                
                # 로그 출력
                print(f"이름: {customer['name']}")
                print(f"여권번호: {customer.get('passport_number', '없음')}")
                print(f"생년월일: {customer.get('birthday', '없음')}")
                print(f"영수증 번호들: {', '.join(customer['receipt_numbers'])}")
                print(f"매칭 상태: {'여권 정보 수정 필요' if customer.get('needs_update') else '매칭됨'}")
                print("-" * 50)
                
            print("\n=== 매칭되지 않은 영수증 ===")
            for receipt in unmatched:
                print(f"영수증 번호: {receipt.receipt_number}")
                
            return passport_info
            
        else:
            # 기존 롯데 로직
            matched, unmatched = fetch_results(user_id)
            print(f"사용자 {user_id}의 matched 정보: {matched}")
            print("=== 매칭된 영수증과 여권 정보 ===")
            
            passport_info = []
            
            # 고객별로 영수증 그룹화
            customer_receipts = {}
            for receipt_number, excel_name in matched:
                if excel_name not in customer_receipts:
                    customer_receipts[excel_name] = []
                customer_receipts[excel_name].append(receipt_number)
            
            # 각 고객별로 정보 생성
            for excel_name, receipt_numbers in customer_receipts.items():
                # 사용자별 passports 테이블에서 해당 이름의 여권 정보 조회
                passport = db.query(Passport).filter(
                    Passport.name == excel_name,
                    Passport.user_id == user_id
                ).first()
                
                info = {
                    "name": excel_name,
                    "receipt_numbers": receipt_numbers,
                    "passport_number": passport.passport_number if passport else None,
                    "birthday": passport.birthday if passport else None,
                    "needs_update": passport is None or passport.name != excel_name
                }
                passport_info.append(info)
                
                if passport and passport.name == excel_name:
                    print(f"이름: {excel_name}")
                    print(f"여권번호: {passport.passport_number}")
                    print(f"생년월일: {passport.birthday}")
                    print(f"영수증 번호들: {', '.join(receipt_numbers)}")
                    print("매칭 상태: 매칭됨")
                else:
                    print(f"이름: {excel_name}")
                    print("여권번호: 없음")
                    print("생년월일: 없음")
                    print(f"영수증 번호들: {', '.join(receipt_numbers)}")
                    print("매칭 상태: 여권 정보 없음 또는 이름 불일치")
                print("-" * 50)
        
            print("\n=== 매칭되지 않은 영수증 ===")
            for receipt in unmatched:
                print(f"영수증 번호: {receipt.receipt_number}")
        
            return passport_info


def get_unmatched_passports(user_id):
    with SessionLocal() as db:
        # 사용자 조회하여 면세점 타입 확인
        user = db.query(User).filter(User.id == user_id).first()
        
        if user.duty_free_type == DutyFreeType.LOTTE:
            # 롯데: passport 테이블의 이름이 lotte_excel_data에 없는 경우 찾기
            sql = """
            SELECT p.name as passport_name, p.passport_number, p.birthday, p.file_path
            FROM passports p
            LEFT JOIN lotte_excel_data e ON p.name = e.name
            WHERE e.name IS NULL AND p.user_id = :user_id;
            """
        else:
            # 신라: passport 테이블의 이름이 shilla_excel_data에 없는 경우 찾기
            sql = """
            SELECT p.name as passport_name, p.passport_number, p.birthday, p.file_path
            FROM passports p
            LEFT JOIN shilla_excel_data e ON p.name = e.name
            WHERE e.name IS NULL AND p.user_id = :user_id;
            """
            
        unmatched = db.execute(text(sql), {"user_id": user_id}).fetchall()
        
        return [{
            "passport_name": row[0],
            "passport_number": row[1],
            "birthday": row[2],
            "file_path": row[3]
        } for row in unmatched]

def update_passport_matching_status(passport_name: str, is_matched: bool, user_id: int):
    """
    사용자별 여권의 매칭 상태를 업데이트합니다.
    
    Args:
        passport_name (str): 여권 소유자의 이름
        is_matched (bool): 매칭 상태 (True/False)
        user_id (int): 사용자 ID
    """
    with SessionLocal() as db:
        passport = db.query(Passport).filter(
            Passport.name == passport_name,
            Passport.user_id == user_id
        ).first()
        if passport:
            passport.is_matched = is_matched
            db.commit()
            return True
        return False