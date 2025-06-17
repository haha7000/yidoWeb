
# app/services/passportMatching.py - 수정된 버전

from app.models.models import Receipt, ReceiptMatchLog, Passport, User, DutyFreeType
from app.core.database import SessionLocal
from sqlalchemy import text
from datetime import datetime


def fetch_results(user_id, duty_free_type="lotte"):
    """면세점 타입에 따라 결과 반환 - 상세 정보 포함"""
    with SessionLocal() as db:
        if duty_free_type == "shilla":
            # 신라 면세점 결과 조회
            from app.services.shilla_matching import fetch_shilla_results_with_details
            return fetch_shilla_results_with_details(user_id)
        else:
            # 롯데 면세점 결과 조회 - 상세 정보 포함
            # 사용자별 매칭된 영수증과 상세 정보 조회
            matched_sql = """
            SELECT DISTINCT 
                r.receipt_number, 
                rml.excel_name,
                rml.passport_number,
                rml.birthday,
                rml.sales_date,
                rml.category,
                rml.brand,
                rml.product_code,
                rml.discount_amount_krw,
                rml.sales_price_usd,
                rml.net_sales_krw,
                rml.store_branch
            FROM receipts r
            JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number
            WHERE rml.is_matched = TRUE 
            AND r.user_id = :user_id 
            AND rml.user_id = :user_id
            ORDER BY rml.excel_name, r.receipt_number
            """
            matched = db.execute(text(matched_sql), {"user_id": user_id}).fetchall()

            # 사용자별 매칭되지 않은 영수증 번호 조회
            unmatched_sql = """
            SELECT DISTINCT r.*
            FROM receipts r
            JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number
            WHERE rml.is_matched = FALSE 
            AND r.user_id = :user_id 
            AND rml.user_id = :user_id
            """
            unmatched = db.execute(text(unmatched_sql), {"user_id": user_id}).fetchall()

            return matched, unmatched


def matching_passport(user_id, duty_free_type="lotte"):
    """면세점 타입에 따라 여권 매칭 정보 반환 - 상세 정보 포함"""
    with SessionLocal() as db:
        if duty_free_type == "shilla":
            # 신라 면세점용 처리
            from app.services.shilla_matching import fetch_shilla_results_with_details
            matched_list, unmatched = fetch_shilla_results_with_details(user_id)
            
            # 상세 정보를 포함한 passport_info 형태로 변환
            passport_info = []
            for customer in matched_list:
                display_name = customer.get('passport_name') or customer.get('name') or customer.get('excel_name')
                
                info = {
                    "name": display_name,
                    "excel_name": customer.get('excel_name'),
                    "passport_name": customer.get('passport_name'),
                    "receipt_numbers": customer['receipt_numbers'],
                    "receipt_ids": customer.get('receipt_ids', []),
                    "receipt_id_mapping": customer.get('receipt_id_mapping', {}),
                    "passport_number": customer.get('passport_number'),
                    "birthday": customer.get('birthday'),
                    "needs_update": customer.get('needs_update', False),
                    "passport_match_status": customer.get('passport_match_status', '확인 필요'),
                    "passport_status": customer.get('passport_status', 'unknown'),
                    # 상세 매출 정보 추가
                    "sales_details": customer.get('sales_details')
                }
                passport_info.append(info)
                
            return passport_info
            
        else:
            # 롯데 면세점 로직 - 상세 정보 포함
            # 매칭된 데이터에서 상세 정보 조회 (store_branch 포함)
            matched_sql = """
            SELECT DISTINCT 
                rml.excel_name,
                rml.receipt_number,
                rml.passport_number,
                rml.birthday,
                rml.sales_date,
                rml.category,
                rml.brand,
                rml.product_code,
                rml.discount_amount_krw,
                rml.sales_price_usd,
                rml.net_sales_krw,
                rml.store_branch
            FROM receipt_match_log rml
            JOIN receipts r ON r.receipt_number = rml.receipt_number AND r.user_id = rml.user_id
            WHERE rml.is_matched = TRUE 
            AND rml.user_id = :user_id
            ORDER BY rml.excel_name, rml.receipt_number
            """
            matched_results = db.execute(text(matched_sql), {"user_id": user_id}).fetchall()
            
            print(f"사용자 {user_id}의 롯데 매칭 정보 (상세 포함): {len(matched_results)}건")
            
            passport_info = []
            
            # 고객별로 영수증 그룹화
            customer_receipts = {}
            customer_details = {}
            
            for row in matched_results:
                (excel_name, receipt_number, passport_number, birthday,
                 sales_date, category, brand, product_code, 
                 discount_amount_krw, sales_price_usd, net_sales_krw, store_branch) = row
                
                if excel_name not in customer_receipts:
                    customer_receipts[excel_name] = []
                    customer_details[excel_name] = {
                        "passport_number": passport_number,
                        "birthday": birthday,
                        "sales_date": sales_date,
                        "category": category,
                        "brand": brand,
                        "product_code": product_code,
                        "discount_amount_krw": float(discount_amount_krw) if discount_amount_krw else None,
                        "sales_price_usd": float(sales_price_usd) if sales_price_usd else None,
                        "net_sales_krw": float(net_sales_krw) if net_sales_krw else None,
                        "store_branch": store_branch
                    }
                    
                customer_receipts[excel_name].append(receipt_number)
            
            # 각 고객별로 정보 생성
            for excel_name, receipt_numbers in customer_receipts.items():
                # 사용자별 passports 테이블에서 해당 이름의 여권 정보 조회
                passport = db.query(Passport).filter(
                    Passport.name == excel_name,
                    Passport.user_id == user_id
                ).first()
                
                details = customer_details[excel_name]
                
                info = {
                    "name": excel_name,
                    "receipt_numbers": receipt_numbers,
                    "passport_number": details["passport_number"],
                    "birthday": details["birthday"],
                    "needs_update": passport is None or passport.name != excel_name,
                    # 상세 매출 정보 추가
                    "sales_details": {
                        "sales_date": details["sales_date"],
                        "category": details["category"],
                        "brand": details["brand"],
                        "product_code": details["product_code"],
                        "discount_amount_krw": details["discount_amount_krw"],
                        "sales_price_usd": details["sales_price_usd"],
                        "net_sales_krw": details["net_sales_krw"],
                        "store_branch": details["store_branch"]
                    }
                }
                passport_info.append(info)
                
                print(f"고객: {excel_name}")
                print(f"  - 매출일자: {details['sales_date']}")
                print(f"  - 카테고리: {details['category']}")
                print(f"  - 브랜드: {details['brand']}")
                print(f"  - 판매가: ${details['sales_price_usd']}")
                print(f"  - 영수증: {', '.join(receipt_numbers)}")
                print("-" * 50)
        
            # 매칭되지 않은 영수증 조회
            unmatched_sql = """
            SELECT DISTINCT r.*
            FROM receipts r
            JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number
            WHERE rml.is_matched = FALSE 
            AND r.user_id = :user_id 
            AND rml.user_id = :user_id
            """
            unmatched = db.execute(text(unmatched_sql), {"user_id": user_id}).fetchall()
            
            print(f"\n=== 매칭되지 않은 영수증 ===")
            for receipt in unmatched:
                print(f"영수증 번호: {receipt.receipt_number}")
        
            return passport_info


def get_unmatched_passports(user_id):
    """면세점 타입에 관계없이 매칭되지 않은 여권 조회"""
    with SessionLocal() as db:
        # 동적 테이블 조회로 변경
        try:
            # 롯데와 신라 모두에서 매칭되지 않은 여권 조회
            sql = """
            SELECT DISTINCT p.name as passport_name, p.passport_number, p.birthday, p.file_path
            FROM passports p
            WHERE p.user_id = :user_id
            AND p.is_matched = FALSE
            AND NOT EXISTS (
                SELECT 1 FROM lotte_excel_data le WHERE le.name = p.name
                UNION ALL
                SELECT 1 FROM shilla_excel_data se WHERE se.name = p.name
            )
            ORDER BY p.name
            """
            unmatched = db.execute(text(sql), {"user_id": user_id}).fetchall()
            
            return [{
                "passport_name": row[0],
                "passport_number": row[1],
                "birthday": row[2],
                "file_path": row[3]
            } for row in unmatched]
            
        except Exception as e:
            print(f"매칭되지 않은 여권 조회 오류: {e}")
            # 테이블이 없는 경우 기본 조회
            unmatched = db.query(Passport).filter(
                Passport.user_id == user_id,
                Passport.is_matched == False
            ).all()
            
            return [{
                "passport_name": passport.name,
                "passport_number": passport.passport_number,
                "birthday": passport.birthday,
                "file_path": passport.file_path
            } for passport in unmatched]


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