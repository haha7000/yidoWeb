# app/services/shilla_matching.py - 완전한 버전 (향상된 edit_unmatched 지원)

from app.models.models import ShillaReceipt, ReceiptMatchLog, Passport
from app.core.database import SessionLocal
from sqlalchemy.orm import Session
from datetime import datetime
from sqlalchemy import text


def shilla_matching_result(user_id):
    """신라 면세점 전용 매칭 로직 - 간단 버전"""
    with SessionLocal() as session:
        print(f"신라 매칭 시작 (간단 버전) - 사용자 {user_id}")
        
        # 1단계: 영수증 번호 매칭 및 여권번호 업데이트
        sql_update_passport = """
        UPDATE shilla_excel_data se
        SET passport_number = sr.passport_number
        FROM shilla_receipts sr
        WHERE se."receiptNumber"::text = sr.receipt_number  
        AND sr.user_id = :user_id
        AND sr.passport_number IS NOT NULL
        AND sr.passport_number != ''
        AND (se.passport_number IS NULL OR se.passport_number = '' OR se.passport_number != sr.passport_number)
        """
        updated_rows = session.execute(text(sql_update_passport), {"user_id": user_id}).rowcount
        print(f"신라 엑셀 데이터에 여권번호 업데이트: {updated_rows}행")
        
        # 2단계: 여권 매칭 상태 업데이트 (개선된 버전)
        sql_update_passport_status = """
        UPDATE passports p
        SET is_matched = TRUE
        FROM shilla_excel_data se
        WHERE p.passport_number = se.passport_number
        AND p.user_id = :user_id
        AND se.passport_number IS NOT NULL
        AND se.passport_number != ''
        AND p.is_matched = FALSE
        """
        passport_updated1 = session.execute(text(sql_update_passport_status), {"user_id": user_id}).rowcount
        
        # 영수증에서 직접 매칭되는 여권들도 업데이트
        sql_update_passport_from_receipt = """
        UPDATE passports p
        SET is_matched = TRUE
        FROM shilla_receipts sr
        WHERE p.passport_number = sr.passport_number
        AND p.user_id = :user_id
        AND sr.passport_number IS NOT NULL
        AND sr.passport_number != ''
        AND p.is_matched = FALSE
        """
        passport_updated2 = session.execute(text(sql_update_passport_from_receipt), {"user_id": user_id}).rowcount
        
        print(f"여권 매칭 상태 업데이트: 엑셀 {passport_updated1}개, 영수증 {passport_updated2}개")
        
        # 3단계: 포괄적인 영수증 매칭 결과 조회 (중복 방지 - 각 영수증 번호당 하나의 레코드만)
        sql_matching = """
        SELECT DISTINCT 
            sr.receipt_number,
            CASE
                WHEN se_first."receiptNumber" IS NOT NULL THEN TRUE
                ELSE FALSE 
            END AS is_matched,
            se_first.name as excel_name,
            sr.passport_number as receipt_passport_number,
            se_first.passport_number as excel_passport_number,
            p.name as passport_name,
            p.birthday as passport_birthday,
            p.is_matched as passport_is_matched,
            -- 신라 추가 정보
            se_first."매출일자" as sales_date,
            se_first."카테고리" as category,
            se_first."브랜드명" as brand,
            se_first."상품코드" as product_code,
            se_first."할인액(￦)" as discount_amount_krw,
            se_first."판매가($)" as sales_price_usd,
            se_first."순매출액(￦)" as net_sales_krw,
            se_first."점" as store_branch
        FROM shilla_receipts sr
        LEFT JOIN (
            SELECT DISTINCT ON ("receiptNumber") 
                "receiptNumber", name, passport_number, "매출일자", "카테고리", "브랜드명", 
                "상품코드", "할인액(￦)", "판매가($)", "순매출액(￦)", "점"
            FROM shilla_excel_data
            ORDER BY "receiptNumber", name
        ) se_first ON se_first."receiptNumber"::text = sr.receipt_number
        LEFT JOIN passports p
          ON (sr.passport_number = p.passport_number OR se_first.passport_number = p.passport_number) 
          AND p.user_id = :user_id
        WHERE sr.user_id = :user_id
        ORDER BY sr.receipt_number
        """
        
        results = session.execute(text(sql_matching), {"user_id": user_id}).fetchall()
        print(f"신라 매칭 결과 조회: {len(results)}개")
        
        # 4단계: 매칭 로그 업데이트 또는 생성
        for row in results:
            (receipt_number, is_matched, excel_name, receipt_passport_number, 
             excel_passport_number, passport_name, passport_birthday, 
             passport_is_matched, sales_date, category, brand,
             product_code, discount_amount_krw, sales_price_usd, net_sales_krw, store_branch) = row
            
            # 최종 여권번호 결정
            final_passport_number = receipt_passport_number or excel_passport_number
            
            # 신라 면세점의 경우: 여권과 매칭이 완료되면 여권의 실제 이름을 사용
            final_excel_name = excel_name
            if final_passport_number and passport_name:
                final_excel_name = passport_name
            
            print(f"신라 영수증: {receipt_number}, 매칭: {is_matched}, 이름: {final_excel_name}")
            if is_matched:
                print(f"  - 매출일자: {sales_date}")
                print(f"  - 카테고리: {category}")
                print(f"  - 브랜드명: {brand}")
                print(f"  - 상품코드: {product_code}")
                print(f"  - 할인액(원): {discount_amount_krw}")
                print(f"  - 판매가($): {sales_price_usd}")
                print(f"  - 순매출액(원): {net_sales_krw}")
                print(f"  - 점: {store_branch}")
            
            # 날짜 변환 처리
            parsed_sales_date = None
            if sales_date:
                try:
                    if isinstance(sales_date, str):
                        parsed_sales_date = datetime.strptime(sales_date, '%Y-%m-%d').date()
                    elif hasattr(sales_date, 'date'):
                        parsed_sales_date = sales_date.date()
                    else:
                        parsed_sales_date = sales_date
                except (ValueError, AttributeError) as e:
                    print(f"날짜 파싱 오류: {sales_date} - {e}")
                    parsed_sales_date = None
            
            # 숫자 변환 처리 함수
            def safe_float(value):
                if value is None:
                    return None
                try:
                    if isinstance(value, str):
                        # 쉼표, 통화기호 제거 후 변환
                        value = value.replace(',', '').replace('￦', '').replace('$', '').strip()
                    return float(value) if value != '' else None
                except (ValueError, TypeError, AttributeError):
                    return None
            
            # 기존 매칭 로그 조회 (더 정확한 조건으로 중복 방지)
            existing_log = session.query(ReceiptMatchLog).filter(
                ReceiptMatchLog.receipt_number == receipt_number,
                ReceiptMatchLog.user_id == user_id,
                ReceiptMatchLog.duty_free_type == "shilla"
            ).first()
            
            if existing_log:
                # 기존 로그 업데이트
                existing_log.is_matched = is_matched
                existing_log.excel_name = final_excel_name if is_matched else None
                existing_log.passport_number = final_passport_number
                existing_log.birthday = passport_birthday
                # 상세 정보 업데이트
                existing_log.sales_date = parsed_sales_date if is_matched else None
                existing_log.category = category if is_matched else None
                existing_log.brand = brand if is_matched else None
                existing_log.product_code = product_code if is_matched else None
                existing_log.discount_amount_krw = safe_float(discount_amount_krw) if is_matched else None
                existing_log.sales_price_usd = safe_float(sales_price_usd) if is_matched else None
                existing_log.net_sales_krw = safe_float(net_sales_krw) if is_matched else None
                existing_log.store_branch = store_branch if is_matched else None
                print(f"매칭 로그 업데이트: {receipt_number} (매칭={is_matched})")
            else:
                # 새 로그 생성
                match_log = ReceiptMatchLog(
                    user_id=user_id,
                    receipt_number=receipt_number,
                    is_matched=is_matched,
                    excel_name=final_excel_name if is_matched else None,
                    passport_number=final_passport_number,
                    birthday=passport_birthday,
                    # 상세 정보
                    sales_date=parsed_sales_date if is_matched else None,
                    category=category if is_matched else None,
                    brand=brand if is_matched else None,
                    product_code=product_code if is_matched else None,
                    discount_amount_krw=safe_float(discount_amount_krw) if is_matched else None,
                    sales_price_usd=safe_float(sales_price_usd) if is_matched else None,
                    net_sales_krw=safe_float(net_sales_krw) if is_matched else None,
                    store_branch=store_branch if is_matched else None,
                    duty_free_type="shilla"  # 신라 면세점
                )
                session.add(match_log)
                print(f"새 매칭 로그 생성: {receipt_number} (매칭={is_matched})")

        session.commit()
        print("신라 매칭 결과 저장 완료")


def fetch_shilla_results(user_id):
    """
    신라 면세점 결과 조회 - 기본 버전 (이전 버전과 호환성 유지)
    """
    with SessionLocal() as db:
        print(f"신라 결과 조회 시작 - 사용자 {user_id}")
        
        # 매칭된 영수증 정보 조회 - 여권 정보를 우선적으로 가져오기
        matched_sql = """
        SELECT DISTINCT 
            sr.receipt_number,
            se.name as excel_name,
            sr.passport_number as receipt_passport_number,
            se.passport_number as excel_passport_number,
            p.name as passport_name,
            p.birthday as passport_birthday,
            p.is_matched as passport_is_matched,
            CASE 
                WHEN p.passport_number IS NOT NULL AND p.is_matched = TRUE THEN 'passport_matched'
                WHEN p.passport_number IS NOT NULL AND p.is_matched = FALSE THEN 'passport_needs_update'  
                WHEN p.passport_number IS NULL THEN 'passport_missing'
                ELSE 'passport_unknown'
            END as passport_status,
            COALESCE(p.name, se.name) as order_name
        FROM shilla_receipts sr
        JOIN shilla_excel_data se ON se."receiptNumber"::text = sr.receipt_number
        LEFT JOIN passports p ON (sr.passport_number = p.passport_number OR se.passport_number = p.passport_number) 
                               AND p.user_id = :user_id
        WHERE sr.user_id = :user_id
        ORDER BY order_name
        """
        matched = db.execute(text(matched_sql), {"user_id": user_id}).fetchall()
        
        # 매칭되지 않은 영수증 조회
        unmatched_sql = """
        SELECT DISTINCT sr.*
        FROM shilla_receipts sr
        LEFT JOIN shilla_excel_data se ON se."receiptNumber"::text = sr.receipt_number
        WHERE se."receiptNumber" IS NULL AND sr.user_id = :user_id
        """
        unmatched = db.execute(text(unmatched_sql), {"user_id": user_id}).fetchall()
        
        # 매칭된 결과를 고객별로 그룹화 (여권 이름 우선)
        customer_data = {}
        for row in matched:
            (receipt_number, excel_name, receipt_passport_number, 
             excel_passport_number, passport_name, passport_birthday, 
             passport_is_matched, passport_status, order_name) = row
            
            # 표시할 이름 결정: 여권 풀네임 우선, 없으면 엑셀 성씨
            display_name = passport_name if passport_name else excel_name
            # 그룹화 키는 여권번호를 기준으로 (같은 사람의 여러 영수증을 묶기 위해)
            final_passport_number = receipt_passport_number or excel_passport_number
            group_key = final_passport_number if final_passport_number else f"excel_{excel_name}"
            
            if group_key not in customer_data:
                # 매칭 상태 판단
                if passport_status == 'passport_matched':
                    match_status = '매칭됨'
                    needs_update = False
                elif passport_status == 'passport_needs_update':
                    match_status = '여권번호 수정 필요'
                    needs_update = True
                elif passport_status == 'passport_missing':
                    match_status = '여권 정보 없음'
                    needs_update = True
                else:
                    match_status = '확인 필요'
                    needs_update = True
                
                customer_data[group_key] = {
                    'name': display_name,  # 여권 풀네임 우선
                    'excel_name': excel_name,  # 엑셀 성씨
                    'passport_name': passport_name,  # 여권 풀네임
                    'receipt_numbers': [],
                    'passport_number': final_passport_number,
                    'birthday': passport_birthday,
                    'needs_update': needs_update,
                    'passport_match_status': match_status,
                    'passport_status': passport_status
                }
                
                print(f"고객 그룹 생성: {group_key} -> {display_name} (상태: {match_status})")
            
            customer_data[group_key]['receipt_numbers'].append(receipt_number)
        
        matched_list = list(customer_data.values())
        
        print(f"신라 매칭 결과 완료:")
        print(f"  - 매칭된 고객: {len(matched_list)}명")
        print(f"  - 매칭안된 영수증: {len(unmatched)}개")
        
        for customer in matched_list:
            print(f"  - {customer['name']} ({customer['passport_match_status']}): {len(customer['receipt_numbers'])}건")
        
        return matched_list, unmatched


def fetch_shilla_results_with_receipt_ids(user_id):
    """
    신라 면세점 결과 조회 - 영수증 ID도 포함하여 반환 (향상된 버전)
    edit_unmatched에서 수정된 데이터도 반영
    """
    with SessionLocal() as db:
        print(f"신라 결과 조회 시작 (영수증 ID 포함, 향상된 버전) - 사용자 {user_id}")
        
        # 매칭된 영수증 정보 조회 - 향상된 쿼리
        matched_sql = """
        SELECT DISTINCT 
            sr.id as receipt_id,
            sr.receipt_number,
            se.name as excel_name,
            sr.passport_number as receipt_passport_number,
            se.passport_number as excel_passport_number,
            p.name as passport_name,
            p.birthday as passport_birthday,
            p.is_matched as passport_is_matched,
            CASE 
                WHEN p.passport_number IS NOT NULL AND p.is_matched = TRUE THEN 'passport_matched'
                WHEN p.passport_number IS NOT NULL AND p.is_matched = FALSE THEN 'passport_needs_update'  
                WHEN p.passport_number IS NULL AND (sr.passport_number IS NOT NULL OR se.passport_number IS NOT NULL) THEN 'passport_missing'
                WHEN p.passport_number IS NULL AND sr.passport_number IS NULL AND se.passport_number IS NULL THEN 'passport_not_provided'
                ELSE 'passport_unknown'
            END as passport_status,
            COALESCE(p.name, se.name) as order_name,
            se."PayBack" as payback_amount
        FROM shilla_receipts sr
        JOIN shilla_excel_data se ON se."receiptNumber"::text = sr.receipt_number
        LEFT JOIN passports p ON (sr.passport_number = p.passport_number OR se.passport_number = p.passport_number) 
                               AND p.user_id = :user_id
        WHERE sr.user_id = :user_id
        ORDER BY order_name, sr.receipt_number
        """
        matched = db.execute(text(matched_sql), {"user_id": user_id}).fetchall()
        
        # 매칭되지 않은 영수증 조회 (동일)
        unmatched_sql = """
        SELECT DISTINCT sr.*
        FROM shilla_receipts sr
        LEFT JOIN shilla_excel_data se ON se."receiptNumber"::text = sr.receipt_number
        WHERE se."receiptNumber" IS NULL AND sr.user_id = :user_id
        ORDER BY sr.receipt_number
        """
        unmatched = db.execute(text(unmatched_sql), {"user_id": user_id}).fetchall()
        
        # 매칭된 결과를 고객별로 그룹화 (향상된 로직)
        customer_data = {}
        receipt_id_mapping = {}
        
        for row in matched:
            (receipt_id, receipt_number, excel_name, receipt_passport_number, 
             excel_passport_number, passport_name, passport_birthday, 
             passport_is_matched, passport_status, order_name, payback_amount) = row
            
            # 영수증 ID 매핑 저장
            receipt_id_mapping[receipt_number] = receipt_id
            
            # 최종 여권번호 결정
            final_passport_number = receipt_passport_number or excel_passport_number
            
            # 신라 면세점의 경우: 여권과 매칭이 완료되면 여권의 실제 이름을 사용
            final_excel_name = excel_name
            if final_passport_number and passport_name:
                final_excel_name = passport_name
            
            # 표시할 이름 결정: 여권 풀네임 우선, 없으면 엑셀 성씨
            display_name = passport_name if passport_name else excel_name
            
            # 그룹화 키 결정 (여권번호 기준, 없으면 엑셀명 기준)
            if final_passport_number:
                group_key = f"passport_{final_passport_number}"
            else:
                group_key = f"excel_{excel_name}_{receipt_number}"  # 여권번호가 없으면 개별 처리
            
            if group_key not in customer_data:
                # 매칭 상태 판단 (향상된 로직)
                if passport_status == 'passport_matched':
                    match_status = '매칭됨'
                    needs_update = False
                elif passport_status == 'passport_needs_update':
                    match_status = '여권번호 수정 필요'
                    needs_update = True
                elif passport_status == 'passport_missing':
                    match_status = '여권 정보 없음'
                    needs_update = True
                elif passport_status == 'passport_not_provided':
                    match_status = '여권번호 미제공'
                    needs_update = True
                else:
                    match_status = '확인 필요'
                    needs_update = True
                
                customer_data[group_key] = {
                    'name': display_name,  # 여권 풀네임 우선
                    'excel_name': excel_name,  # 엑셀 성씨
                    'passport_name': passport_name,  # 여권 풀네임
                    'receipt_numbers': [],
                    'receipt_ids': [],  # 영수증 ID 목록
                    'passport_number': final_passport_number,
                    'birthday': passport_birthday,
                    'needs_update': needs_update,
                    'passport_match_status': match_status,
                    'passport_status': passport_status,
                    'payback_amount': payback_amount
                }
                
                print(f"고객 그룹 생성: {group_key} -> {display_name} (상태: {match_status})")
            
            customer_data[group_key]['receipt_numbers'].append(receipt_number)
            customer_data[group_key]['receipt_ids'].append(receipt_id)
        
        matched_list = list(customer_data.values())
        
        # 영수증 ID 매핑도 함께 반환
        for customer in matched_list:
            customer['receipt_id_mapping'] = {
                receipt_num: receipt_id_mapping.get(receipt_num) 
                for receipt_num in customer['receipt_numbers']
            }
        
        print(f"신라 매칭 결과 완료 (향상된 버전):")
        print(f"  - 매칭된 고객: {len(matched_list)}명")
        print(f"  - 매칭안된 영수증: {len(unmatched)}개")
        
        for customer in matched_list:
            print(f"  - {customer['name']} ({customer['passport_match_status']}): {len(customer['receipt_numbers'])}건")
        
        return matched_list, unmatched


def get_shilla_unmatched_passports(user_id):
    """
    신라 면세점 전용 매칭안된 여권 조회 (향상된 버전)
    edit_unmatched에서 수정된 데이터도 고려
    """
    with SessionLocal() as db:
        print(f"신라 매칭안된 여권 조회 (향상된 버전) - 사용자 {user_id}")
        
        # 향상된 쿼리: 영수증 테이블의 여권번호도 고려
        sql = """
        SELECT DISTINCT 
            p.name as passport_name, 
            p.passport_number, 
            p.birthday, 
            p.file_path,
            p.is_matched,
            CASE 
                WHEN se.passport_number IS NOT NULL OR sr.passport_number IS NOT NULL THEN 'has_connection'
                ELSE 'no_connection'
            END as connection_status,
            CASE 
                WHEN se."receiptNumber" IS NOT NULL THEN 'excel_matched'
                ELSE 'excel_not_matched'
            END as excel_match_status
        FROM passports p
        LEFT JOIN shilla_excel_data se ON p.passport_number = se.passport_number
        LEFT JOIN shilla_receipts sr ON p.passport_number = sr.passport_number AND sr.user_id = :user_id
        WHERE p.user_id = :user_id
        AND (
            p.is_matched = FALSE 
            OR (se.passport_number IS NULL AND sr.passport_number IS NULL)
            OR p.passport_number IS NULL
            OR p.passport_number = ''
        )
        ORDER BY p.name
        """
        
        unmatched = db.execute(text(sql), {"user_id": user_id}).fetchall()
        
        result = []
        for row in unmatched:
            (passport_name, passport_number, birthday, file_path, 
             is_matched, connection_status, excel_match_status) = row
            
            result.append({
                "passport_name": passport_name,
                "passport_number": passport_number,
                "birthday": birthday,
                "file_path": file_path,
                "is_matched": is_matched,
                "connection_status": connection_status,
                "excel_match_status": excel_match_status
            })
            
            print(f"매칭안된 여권: {passport_name} ({passport_number}) - "
                  f"is_matched: {is_matched}, connection: {connection_status}, excel: {excel_match_status}")
        
        print(f"매칭안된 여권 총 {len(result)}개")
        return result


def get_shilla_receipt_id_by_receipt_number(receipt_number, user_id):
    """
    신라 영수증 번호로 ShillaReceipt ID를 조회하는 함수
    """
    with SessionLocal() as db:
        receipt = db.query(ShillaReceipt).filter(
            ShillaReceipt.receipt_number == receipt_number,
            ShillaReceipt.user_id == user_id
        ).first()
        
        return receipt.id if receipt else None


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
    

def fetch_shilla_results_with_details(user_id):
    """
    신라 면세점 결과 조회 - 상세 매출 정보 포함
    """
    with SessionLocal() as db:
        print(f"신라 결과 조회 시작 (상세 정보 포함) - 사용자 {user_id}")
        
        # 매칭된 영수증 정보 조회 - 상세 정보 포함 (additional_data 제거)
        matched_sql = """
        SELECT DISTINCT 
            sr.id as receipt_id,
            sr.receipt_number,
            se.name as excel_name,
            sr.passport_number as receipt_passport_number,
            se.passport_number as excel_passport_number,
            p.name as passport_name,
            p.birthday as passport_birthday,
            p.is_matched as passport_is_matched,
            CASE 
                WHEN p.passport_number IS NOT NULL AND p.is_matched = TRUE THEN 'passport_matched'
                WHEN p.passport_number IS NOT NULL AND p.is_matched = FALSE THEN 'passport_needs_update'  
                WHEN p.passport_number IS NULL AND (sr.passport_number IS NOT NULL OR se.passport_number IS NOT NULL) THEN 'passport_missing'
                WHEN p.passport_number IS NULL AND sr.passport_number IS NULL AND se.passport_number IS NULL THEN 'passport_not_provided'
                ELSE 'passport_unknown'
            END as passport_status,
            COALESCE(p.name, se.name) as order_name,
            se."PayBack" as payback_amount,
            -- 신라 상세 정보 (receipt_match_log에서 가져오기)
            rml.sales_date,
            rml.category,
            rml.brand,
            rml.product_code,
            rml.discount_amount_krw,
            rml.sales_price_usd,
            rml.net_sales_krw
        FROM shilla_receipts sr
        JOIN shilla_excel_data se ON se."receiptNumber"::text = sr.receipt_number
        LEFT JOIN passports p ON (sr.passport_number = p.passport_number OR se.passport_number = p.passport_number) 
                               AND p.user_id = :user_id
        LEFT JOIN receipt_match_log rml ON rml.receipt_number = sr.receipt_number 
                                        AND rml.user_id = :user_id
        WHERE sr.user_id = :user_id
        ORDER BY order_name, sr.receipt_number
        """
        matched = db.execute(text(matched_sql), {"user_id": user_id}).fetchall()
        
        # 매칭되지 않은 영수증 조회
        unmatched_sql = """
        SELECT DISTINCT sr.*
        FROM shilla_receipts sr
        LEFT JOIN shilla_excel_data se ON se."receiptNumber"::text = sr.receipt_number
        WHERE se."receiptNumber" IS NULL AND sr.user_id = :user_id
        ORDER BY sr.receipt_number
        """
        unmatched = db.execute(text(unmatched_sql), {"user_id": user_id}).fetchall()
        
        # 매칭된 결과를 고객별로 그룹화 (상세 정보 포함)
        customer_data = {}
        receipt_id_mapping = {}
        
        for row in matched:
            (receipt_id, receipt_number, excel_name, receipt_passport_number, 
             excel_passport_number, passport_name, passport_birthday, 
             passport_is_matched, passport_status, order_name, payback_amount,
             sales_date, category, brand, product_code, 
             discount_amount_krw, sales_price_usd, net_sales_krw) = row
            
            # 영수증 ID 매핑 저장
            receipt_id_mapping[receipt_number] = receipt_id
            
            # 최종 여권번호 결정
            final_passport_number = receipt_passport_number or excel_passport_number
            
            # 신라 면세점의 경우: 여권과 매칭이 완료되면 여권의 실제 이름을 사용
            final_excel_name = excel_name
            if final_passport_number and passport_name:
                final_excel_name = passport_name
            
            # 표시할 이름 결정: 여권 풀네임 우선, 없으면 엑셀 성씨
            display_name = passport_name if passport_name else excel_name
            
            # 그룹화 키 결정
            if final_passport_number:
                group_key = f"passport_{final_passport_number}"
            else:
                group_key = f"excel_{excel_name}_{receipt_number}"
            
            if group_key not in customer_data:
                # 매칭 상태 판단
                if passport_status == 'passport_matched':
                    match_status = '매칭됨'
                    needs_update = False
                elif passport_status == 'passport_needs_update':
                    match_status = '여권번호 수정 필요'
                    needs_update = True
                elif passport_status == 'passport_missing':
                    match_status = '여권 정보 없음'
                    needs_update = True
                elif passport_status == 'passport_not_provided':
                    match_status = '여권번호 미제공'
                    needs_update = True
                else:
                    match_status = '확인 필요'
                    needs_update = True
                
                customer_data[group_key] = {
                    'name': display_name,
                    'excel_name': excel_name,
                    'passport_name': passport_name,
                    'receipt_numbers': [],
                    'receipt_ids': [],
                    'passport_number': final_passport_number,
                    'birthday': passport_birthday,
                    'needs_update': needs_update,
                    'passport_match_status': match_status,
                    'passport_status': passport_status,
                    'payback_amount': payback_amount,
                    # 상세 매출 정보 추가
                    'sales_details': {
                        'sales_date': sales_date,
                        'category': category,
                        'brand': brand,
                        'product_code': product_code,
                        'discount_amount_krw': float(discount_amount_krw) if discount_amount_krw else None,
                        'sales_price_usd': float(sales_price_usd) if sales_price_usd else None,
                        'net_sales_krw': float(net_sales_krw) if net_sales_krw else None
                    }
                }
                
                print(f"고객 그룹 생성 (상세 정보 포함): {group_key} -> {display_name}")
                print(f"  - 매출일자: {sales_date}")
                print(f"  - 카테고리: {category}")
                print(f"  - 브랜드: {brand}")
                print(f"  - 상태: {match_status}")
            
            customer_data[group_key]['receipt_numbers'].append(receipt_number)
            customer_data[group_key]['receipt_ids'].append(receipt_id)
        
        matched_list = list(customer_data.values())
        
        # 영수증 ID 매핑도 함께 반환
        for customer in matched_list:
            customer['receipt_id_mapping'] = {
                receipt_num: receipt_id_mapping.get(receipt_num) 
                for receipt_num in customer['receipt_numbers']
            }
        
        print(f"신라 매칭 결과 완료 (상세 정보 포함):")
        print(f"  - 매칭된 고객: {len(matched_list)}명")
        print(f"  - 매칭안된 영수증: {len(unmatched)}개")
        
        return matched_list, unmatched