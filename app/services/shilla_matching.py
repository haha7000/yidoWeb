# app/services/shilla_matching.py - 완전한 버전 (향상된 edit_unmatched 지원)

from app.models.models import ShillaReceipt, ReceiptMatchLog, Passport
from app.core.database import SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy import text


def shilla_matching_result(user_id):
    """
    신라 면세점 전용 매칭 로직 - 향상된 버전
    1. ShillaReceipt.receiptNumber를 shilla_excel_data.receiptNumber와 매칭
    2. 매칭된 경우 shilla_excel_data에 passportNumber 업데이트
    3. shilla_excel_data.passportNumber를 passports.passport_number와 매칭하여 이름과 생일 가져오기
    4. edit_unmatched에서 수정된 데이터도 반영
    """
    with SessionLocal() as session:
        print(f"신라 매칭 시작 (향상된 버전) - 사용자 {user_id}")
        
        # 1단계: 영수증 번호 매칭 및 여권번호 업데이트
        # ShillaReceipt에서 여권번호가 있는 경우 우선적으로 사용
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
        
        # 2단계: 여권 매칭 상태 업데이트 (자동 매칭)
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
        passport_updated = session.execute(text(sql_update_passport_status), {"user_id": user_id}).rowcount
        print(f"자동 여권 매칭 상태 업데이트: {passport_updated}개")
        
        # 3단계: 수동으로 연결된 여권들도 매칭 상태 업데이트
        sql_manual_passport_update = """
        UPDATE passports p
        SET is_matched = TRUE
        FROM shilla_receipts sr
        WHERE p.passport_number = sr.passport_number
        AND p.user_id = :user_id
        AND sr.user_id = :user_id
        AND sr.passport_number IS NOT NULL
        AND sr.passport_number != ''
        AND p.is_matched = FALSE
        """
        manual_updated = session.execute(text(sql_manual_passport_update), {"user_id": user_id}).rowcount
        print(f"수동 여권 매칭 상태 업데이트: {manual_updated}개")
        
        # 4단계: 포괄적인 영수증 매칭 결과 로그 저장/업데이트
        sql_matching = """
        SELECT DISTINCT 
            sr.receipt_number,
            CASE
                WHEN se."receiptNumber" IS NOT NULL THEN TRUE
                ELSE FALSE 
            END AS is_matched,
            se.name as excel_name,
            sr.passport_number as receipt_passport_number,
            se.passport_number as excel_passport_number,
            p.name as passport_name,
            p.birthday as passport_birthday,
            p.is_matched as passport_is_matched,
            se."PayBack" as payback_amount
        FROM shilla_receipts sr
        LEFT JOIN shilla_excel_data se
          ON se."receiptNumber"::text = sr.receipt_number
        LEFT JOIN passports p
          ON (sr.passport_number = p.passport_number OR se.passport_number = p.passport_number) 
          AND p.user_id = :user_id
        WHERE sr.user_id = :user_id
        ORDER BY sr.receipt_number
        """
        
        results = session.execute(text(sql_matching), {"user_id": user_id}).fetchall()
        print(f"매칭 결과 조회: {len(results)}개")
        
        # 5단계: 매칭 로그 업데이트 또는 생성
        for row in results:
            (receipt_number, is_matched, excel_name, receipt_passport_number, 
             excel_passport_number, passport_name, passport_birthday, 
             passport_is_matched, payback_amount) = row
            
            # 최종 여권번호 결정 (영수증의 여권번호 우선, 없으면 엑셀의 여권번호)
            final_passport_number = receipt_passport_number or excel_passport_number
            
            # 기존 매칭 로그 조회
            existing_log = session.query(ReceiptMatchLog).filter(
                ReceiptMatchLog.receipt_number == receipt_number,
                ReceiptMatchLog.user_id == user_id
            ).first()
            
            if existing_log:
                # 기존 로그 업데이트
                existing_log.is_matched = is_matched
                existing_log.excel_name = excel_name if is_matched else None
                existing_log.passport_number = final_passport_number
                existing_log.birthday = passport_birthday
                print(f"매칭 로그 업데이트: {receipt_number} (매칭={is_matched})")
            else:
                # 새 로그 생성
                match_log = ReceiptMatchLog(
                    user_id=user_id,
                    receipt_number=receipt_number,
                    is_matched=is_matched,
                    excel_name=excel_name if is_matched else None,
                    passport_number=final_passport_number,
                    birthday=passport_birthday
                )
                session.add(match_log)
                print(f"새 매칭 로그 생성: {receipt_number} (매칭={is_matched})")

        # 6단계: 매칭되지 않은 여권들의 상태도 확인
        sql_unmatched_passports = """
        UPDATE passports p
        SET is_matched = FALSE
        WHERE p.user_id = :user_id
        AND p.passport_number NOT IN (
            SELECT DISTINCT se.passport_number 
            FROM shilla_excel_data se 
            WHERE se.passport_number IS NOT NULL 
            AND se.passport_number != ''
        )
        AND p.passport_number NOT IN (
            SELECT DISTINCT sr.passport_number 
            FROM shilla_receipts sr 
            JOIN shilla_excel_data se2 ON se2."receiptNumber"::text = sr.receipt_number
            WHERE sr.passport_number IS NOT NULL 
            AND sr.passport_number != ''
            AND sr.user_id = :user_id
        )
        AND p.is_matched = TRUE
        """
        unmatched_passport_count = session.execute(text(sql_unmatched_passports), {"user_id": user_id}).rowcount
        print(f"매칭 해제된 여권: {unmatched_passport_count}개")

        session.commit()
        print("신라 매칭 결과 저장 완료 (향상된 버전)")


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