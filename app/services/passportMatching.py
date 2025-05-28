from app.models.models import Receipt, ReceiptMatchLog, Passport
from app.core.database import SessionLocal
from sqlalchemy import text

def fetch_results():
    with SessionLocal() as db:
        # 매칭된 영수증 번호와 이름 조회
        sql = """
        SELECT r.receipt_number, e."name"
        FROM receipts r
        JOIN receipt_match_log m ON r.receipt_number = m.receipt_number
        JOIN excel_data e ON r.receipt_number = e."receiptNumber"
        WHERE m.is_matched = TRUE;
        """
        matched = db.execute(text(sql)).fetchall()

        # 매칭되지 않은 영수증 번호 조회
        unmatched_sql = """
        SELECT r.*
        FROM receipts r
        JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number
        WHERE rml.is_matched = FALSE
        """
        unmatched = db.execute(text(unmatched_sql)).fetchall()

        return matched, unmatched
    

def matching_passport():
    matched, unmatched = fetch_results()
    print(f"matched의 정보는 {matched} 입니다")
    print("=== 매칭된 영수증과 여권 정보 ===")
    passport_info = []
    
    with SessionLocal() as db:
        # 고객별로 영수증 그룹화
        customer_receipts = {}
        for receipt_number, excel_name in matched:
            if excel_name not in customer_receipts:
                customer_receipts[excel_name] = []
            customer_receipts[excel_name].append(receipt_number)
        
        # 각 고객별로 정보 생성
        for excel_name, receipt_numbers in customer_receipts.items():
            # passports 테이블에서 해당 이름의 여권 정보 조회
            passport = db.query(Passport).filter(Passport.name == excel_name).first()
            
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

def get_unmatched_passports():
    with SessionLocal() as db:
        # passport 테이블의 이름이 excel_data에 없는 경우 찾기
        sql = """
        SELECT p.name as passport_name, p.passport_number, p.birthday, p.file_path
        FROM passports p
        LEFT JOIN excel_data e ON p.name = e."name"
        WHERE e."name" IS NULL;
        """
        unmatched = db.execute(text(sql)).fetchall()
        
        return [{
            "passport_name": row[0],
            "passport_number": row[1],
            "birthday": row[2],
            "file_path": row[3]
        } for row in unmatched]

def update_passport_matching_status(passport_name: str, is_matched: bool):
    """
    여권의 매칭 상태를 업데이트합니다.
    
    Args:
        passport_name (str): 여권 소유자의 이름
        is_matched (bool): 매칭 상태 (True/False)
    """
    with SessionLocal() as db:
        passport = db.query(Passport).filter(Passport.name == passport_name).first()
        if passport:
            passport.is_matched = is_matched
            db.commit()
            return True
        return False
    