# app/services/shilla_matching.py - 완전한 버전 (향상된 edit_unmatched 지원)

from app.models.models import ShillaReceipt, ReceiptMatchLog, Passport
from app.core.database import SessionLocal
from app.utils.helpers import safe_float
from sqlalchemy.orm import Session
from datetime import datetime
from sqlalchemy import text


def shilla_matching_result(user_id):
    """신라 면세점 매칭 로직 - 영수증 단위로 매칭 로그 생성 (중복 방지)"""
    
    with SessionLocal() as session:
        print(f"🚀 신라 면세점 매칭 시작 - 사용자 ID: {user_id}")
        print("=" * 60)
        
        # 데이터 현황 확인
        receipt_count = session.execute(text("SELECT COUNT(*) FROM shilla_receipts WHERE user_id = :user_id"), {"user_id": user_id}).scalar()
        excel_count = session.execute(text("SELECT COUNT(*) FROM shilla_excel_data WHERE user_id = :user_id"), {"user_id": user_id}).scalar()
        passport_count = session.execute(text("SELECT COUNT(*) FROM passports WHERE user_id = :user_id"), {"user_id": user_id}).scalar()
        log_count = session.execute(text("SELECT COUNT(*) FROM receipt_match_log WHERE user_id = :user_id AND duty_free_type = 'shilla'"), {"user_id": user_id}).scalar()
        
        print(f"📊 데이터 현황:")
        print(f"   - 신라 영수증: {receipt_count}개")
        print(f"   - 신라 엑셀 데이터: {excel_count}개")
        print(f"   - 여권: {passport_count}개")
        print(f"   - 기존 매칭 로그: {log_count}개")
        
        if receipt_count == 0:
            print("⚠️ 신라 영수증이 없습니다. 매칭을 종료합니다.")
            return
        
        # 1단계: 여권 매칭 상태 업데이트 (여권번호만 기준으로 정확한 매칭)
        sql_update_passport_from_excel = """
        UPDATE passports p
        SET is_matched = TRUE
        FROM shilla_excel_data se
        WHERE p.passport_number = se.passport_number
        AND p.user_id = :user_id
        AND se.user_id = :user_id
        AND se.passport_number IS NOT NULL
        AND se.passport_number != ''
        AND p.passport_number IS NOT NULL
        AND p.passport_number != ''
        AND p.is_matched = FALSE
        """
        passport_updated1 = session.execute(text(sql_update_passport_from_excel), {"user_id": user_id}).rowcount
        
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
        
        # 1.5단계: 영수증과 엑셀이 매칭될 때 엑셀 행에 여권번호 업데이트 (핵심 로직)
        sql_update_excel_passport = """
        UPDATE shilla_excel_data se
        SET passport_number = sr.passport_number
        FROM shilla_receipts sr
        WHERE REPLACE(se."receiptNumber"::text, '.0', '') = sr.receipt_number
        AND sr.user_id = :user_id
        AND se.user_id = :user_id
        AND sr.passport_number IS NOT NULL
        AND sr.passport_number != ''
        AND (se.passport_number IS NULL OR se.passport_number = '')
        """
        excel_passport_updated = session.execute(text(sql_update_excel_passport), {"user_id": user_id}).rowcount
        print(f"🔗 엑셀 데이터에 여권번호 업데이트: {excel_passport_updated}개")
        
        # 2단계: 영수증 단위로 매칭 결과 조회 및 상품 정보 집계
        sql_matching = """
        SELECT 
            sr.receipt_number,
            BOOL_OR(se."receiptNumber" IS NOT NULL) AS is_matched,
            MAX(se.name) as excel_name,
            MAX(sr.passport_number) as receipt_passport_number,
            MAX(se.passport_number) as excel_passport_number,
            MAX(p.name) as passport_name,
            MAX(p.birthday) as passport_birthday,
            BOOL_OR(p.is_matched) as passport_is_matched,
            -- 집계된 상품 정보
            MIN(se."매출일자") as sales_date,
            STRING_AGG(DISTINCT se."카테고리", ', ') as categories,
            STRING_AGG(DISTINCT se."브랜드명", ', ') as brands,
            COUNT(se."상품코드") as product_count,
            SUM(CASE WHEN se."할인액(￦)" IS NOT NULL 
                     THEN CAST(se."할인액(￦)" AS NUMERIC) 
                     ELSE 0 END) as total_discount_krw,
            SUM(CASE WHEN se."판매가($)" IS NOT NULL 
                     THEN CAST(se."판매가($)" AS NUMERIC) 
                     ELSE 0 END) as total_sales_usd,
            SUM(CASE WHEN se."순매출액(￦)" IS NOT NULL 
                     THEN CAST(se."순매출액(￦)" AS NUMERIC) 
                     ELSE 0 END) as total_net_sales_krw,
            MIN(se."점") as store_branch
        FROM shilla_receipts sr
        LEFT JOIN shilla_excel_data se ON REPLACE(se."receiptNumber"::text, '.0', '') = sr.receipt_number AND se.user_id = :user_id
        LEFT JOIN passports p
          ON (p.passport_number = sr.passport_number OR p.passport_number = se.passport_number)
          AND p.user_id = :user_id
          AND p.passport_number IS NOT NULL
          AND p.passport_number != ''
        WHERE sr.user_id = :user_id
        GROUP BY sr.receipt_number
        ORDER BY sr.receipt_number
        """
        
        results = session.execute(text(sql_matching), {"user_id": user_id}).fetchall()
        print(f"신라 매칭 처리할 영수증: {len(results)}개")
        
        # 3단계: 중복 로그 정리 후 기존 로그 조회
        existing_logs_query = session.query(ReceiptMatchLog).filter(
            ReceiptMatchLog.user_id == user_id,
            ReceiptMatchLog.duty_free_type == "shilla"
        ).all()
        
        # 중복 로그 감지 및 정리
        receipt_log_groups = {}
        for log in existing_logs_query:
            if log.receipt_number not in receipt_log_groups:
                receipt_log_groups[log.receipt_number] = []
            receipt_log_groups[log.receipt_number].append(log)
        
        # 중복 로그 제거 (가장 최근 것만 유지)
        existing_logs = {}
        duplicates_removed = 0
        for receipt_number, logs in receipt_log_groups.items():
            if len(logs) > 1:
                # 가장 최근 로그 유지, 나머지 삭제
                logs.sort(key=lambda x: x.checked_at or datetime.min, reverse=True)
                keep_log = logs[0]
                for duplicate_log in logs[1:]:
                    session.delete(duplicate_log)
                    duplicates_removed += 1
                existing_logs[receipt_number] = keep_log
                print(f"🗑️ 중복 로그 정리: {receipt_number} ({len(logs)-1}개 삭제)")
            else:
                existing_logs[receipt_number] = logs[0]
        
        if duplicates_removed > 0:
            session.commit()
            print(f"🔧 중복 로그 정리 완료: {duplicates_removed}개 삭제")
        
        print(f"기존 신라 매칭 로그: {len(existing_logs)}개 (중복 제거 후)")
        
        # 4단계: 영수증 단위 매칭 로그 업데이트/생성 (선택적 처리)
        processed_receipts = set()
        
        for row in results:
            (receipt_number, is_matched, excel_name, receipt_passport_number, 
             excel_passport_number, passport_name, passport_birthday, 
             passport_is_matched, sales_date, categories, brands,
             product_count, total_discount_krw, total_sales_usd, total_net_sales_krw, 
             store_branch) = row
            
            # 최종 여권번호 결정 - 여권 테이블과 매칭되는 번호 우선
            final_passport_number = None
            if passport_name:  # 여권 테이블과 매칭된 경우
                # 여권 테이블과 매칭되는 번호를 우선 사용
                if excel_passport_number and passport_name:
                    final_passport_number = excel_passport_number
                elif receipt_passport_number and passport_name:
                    final_passport_number = receipt_passport_number
            else:
                # 여권 테이블과 매칭되지 않은 경우 기존 로직 사용
                final_passport_number = receipt_passport_number or excel_passport_number
            
            print(f"📋 여권번호 결정: 영수증({receipt_passport_number}) vs 엑셀({excel_passport_number}) -> 최종({final_passport_number})")
            print(f"📋 여권 이름: {passport_name}")
            
            # 신라 면세점의 경우: 여권과 매칭이 완료되면 여권의 실제 이름을 사용
            final_excel_name = excel_name
            if final_passport_number and passport_name:
                print(f"🔄 여권 이름으로 업데이트: {excel_name} -> {passport_name} (여권번호: {final_passport_number})")
                final_excel_name = passport_name
            else:
                print(f"📋 엑셀 이름 유지: {excel_name} (여권번호: {final_passport_number}, 여권이름: {passport_name})")
            
            print(f"신라 영수증: {receipt_number}, 매칭: {is_matched}, 최종이름: {final_excel_name}")
            if is_matched:
                print(f"  - 매출일자: {sales_date}")
                print(f"  - 카테고리: {categories}")
                print(f"  - 브랜드명: {brands}")
                print(f"  - 상품 수: {product_count}")
                print(f"  - 총 할인액(원): {total_discount_krw}")
                print(f"  - 총 판매가($): {total_sales_usd}")
                print(f"  - 총 순매출액(원): {total_net_sales_krw}")
                print(f"  - 점: {store_branch}")
            
            # 날짜 변환 처리
            parsed_sales_date = None
            if sales_date:
                try:
                    if isinstance(sales_date, str):
                        # 날짜 부분만 추출 (시간 부분 제거)
                        date_part = sales_date.split()[0] if ' ' in sales_date else sales_date
                        parsed_sales_date = datetime.strptime(date_part, '%Y-%m-%d').date()
                    elif hasattr(sales_date, 'date'):
                        parsed_sales_date = sales_date.date()
                    else:
                        parsed_sales_date = sales_date
                except (ValueError, AttributeError) as e:
                    print(f"날짜 파싱 오류: {sales_date} - {e}")
                    parsed_sales_date = None
            
            # 기존 로그가 있으면 업데이트, 없으면 새로 생성
            if receipt_number in existing_logs:
                match_log = existing_logs[receipt_number]
                
                # 최근에 수동으로 업데이트된 로그인지 확인 (30초 이내)
                recent_manual_update = False
                if match_log.checked_at:
                    time_diff = datetime.now() - match_log.checked_at
                    if time_diff.total_seconds() < 30:  # 30초 = 여권 이름 업데이트는 거의 즉시 허용
                        recent_manual_update = True
                        print(f"🔒 최근 수동 업데이트된 로그 보호: {receipt_number} (업데이트: {match_log.checked_at})")
                    elif final_passport_number and passport_name and match_log.excel_name != passport_name:
                        # 여권 이름으로 업데이트하는 경우는 보호 시간을 무시
                        print(f"🔄 여권 이름 업데이트를 위해 보호 무시: {receipt_number}")
                        recent_manual_update = False
                
                if not recent_manual_update:
                    # 자동 매칭 로직으로 업데이트
                    old_name = match_log.excel_name
                    match_log.is_matched = is_matched
                    match_log.excel_name = final_excel_name
                    match_log.passport_number = final_passport_number
                    match_log.birthday = passport_birthday
                    match_log.sales_date = parsed_sales_date
                    match_log.category = categories
                    match_log.brand = brands
                    match_log.product_code = f"TOTAL_{product_count}_ITEMS"
                    match_log.discount_amount_krw = safe_float(total_discount_krw)
                    match_log.sales_price_usd = safe_float(total_sales_usd)
                    match_log.net_sales_krw = safe_float(total_net_sales_krw)
                    match_log.store_branch = store_branch
                    # checked_at은 수동 업데이트 시에만 갱신, 자동 매칭에서는 유지
                    print(f"🔄 기존 매칭 로그 자동 업데이트: {receipt_number}")
                    print(f"   이름 변경: {old_name} -> {final_excel_name}")
                    print(f"   여권번호: {final_passport_number}")
                else:
                    print(f"⏭️ 수동 업데이트 로그 건너뜀: {receipt_number}")
            else:
                # 새 매칭 로그 생성
                match_log = ReceiptMatchLog(
                    user_id=user_id,
                    receipt_number=receipt_number,
                    is_matched=is_matched,
                    excel_name=final_excel_name,
                    passport_number=final_passport_number,
                    birthday=passport_birthday,
                    sales_date=parsed_sales_date,
                    category=categories,
                    brand=brands,
                    product_code=f"TOTAL_{product_count}_ITEMS",
                    discount_amount_krw=safe_float(total_discount_krw),
                    sales_price_usd=safe_float(total_sales_usd),
                    net_sales_krw=safe_float(total_net_sales_krw),
                    store_branch=store_branch,
                    duty_free_type="shilla"
                )
                session.add(match_log)
                print(f"✨ 새 매칭 로그 생성: {receipt_number}")
                print(f"   이름: {final_excel_name}")
                print(f"   여권번호: {final_passport_number}")
                print(f"   매칭상태: {is_matched}")
            
            processed_receipts.add(receipt_number)
                
            print(f"영수증 단위 매칭 로그 처리: {receipt_number} ({product_count}개 상품)")

        # 5단계: 더 이상 존재하지 않는 영수증의 로그 정리 (선택적 삭제)
        obsolete_receipts = set(existing_logs.keys()) - processed_receipts
        if obsolete_receipts:
            print(f"더 이상 존재하지 않는 영수증 로그 {len(obsolete_receipts)}개 정리 중...")
            for obsolete_receipt in obsolete_receipts:
                session.delete(existing_logs[obsolete_receipt])
                print(f"  - 삭제: {obsolete_receipt}")
        
        session.commit()
        print(f"✅ 신라 매칭 로직 완료:")
        print(f"  - 처리된 영수증: {len(processed_receipts)}개")
        print(f"  - 업데이트된 로그: {len([r for r in processed_receipts if r in existing_logs])}개") 
        print(f"  - 새로 생성된 로그: {len([r for r in processed_receipts if r not in existing_logs])}개")
        print(f"  - 정리된 obsolete 로그: {len(obsolete_receipts)}개")
        
        # 5단계: 수수료 계산 후 영수증별 수수료 합계를 shilla_receipts에 업데이트
        print("수수료 계산을 먼저 실행해주세요. (할인율·수수료 계산 버튼 클릭)")
        print("수수료 계산 완료 후 update_commission_totals() 함수를 호출하세요.")


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
        JOIN shilla_excel_data se ON REPLACE(se."receiptNumber"::text, '.0', '') = sr.receipt_number AND se.user_id = :user_id
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
        LEFT JOIN shilla_excel_data se ON REPLACE(se."receiptNumber"::text, '.0', '') = sr.receipt_number AND se.user_id = :user_id
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
        LEFT JOIN shilla_excel_data se ON p.passport_number = se.passport_number AND se.user_id = :user_id
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
        print(f"🔎 신라 결과 조회 시작 (상세 정보 포함) - 사용자 {user_id}")
        
        # 현재 receipt_match_log 상태 먼저 확인
        log_count_sql = "SELECT COUNT(*) FROM receipt_match_log WHERE user_id = :user_id AND duty_free_type = 'shilla'"
        log_count = db.execute(text(log_count_sql), {"user_id": user_id}).scalar()
        print(f"📊 현재 신라 매칭 로그 수: {log_count}개")
        
        # 영수증 정보 조회 - receipt_match_log 기반으로 매칭/미매칭 구분
        all_receipts_sql = """
        SELECT DISTINCT 
            sr.id as receipt_id,
            sr.receipt_number,
            COALESCE(se.name, rml.excel_name) as excel_name,
            sr.passport_number as receipt_passport_number,
            COALESCE(se.passport_number, rml.passport_number) as excel_passport_number,
            p.name as passport_name,
            p.birthday as passport_birthday,
            p.is_matched as passport_is_matched,
            CASE 
                WHEN p.passport_number IS NOT NULL AND p.is_matched = TRUE THEN 'passport_matched'
                WHEN p.passport_number IS NOT NULL AND p.is_matched = FALSE THEN 'passport_needs_update'  
                WHEN p.passport_number IS NULL AND (sr.passport_number IS NOT NULL OR COALESCE(se.passport_number, rml.passport_number) IS NOT NULL) THEN 'passport_missing'
                WHEN p.passport_number IS NULL AND sr.passport_number IS NULL AND COALESCE(se.passport_number, rml.passport_number) IS NULL THEN 'passport_missing'
                ELSE 'passport_unknown'
            END as passport_status,
            COALESCE(p.name, se.name, rml.excel_name) as order_name,
            -- 신라 상세 정보 (receipt_match_log에서 우선 가져오기)
            rml.sales_date,
            rml.category,
            rml.brand,
            rml.product_code,
            rml.discount_amount_krw,
            rml.sales_price_usd,
            rml.net_sales_krw,
            -- 매칭 상태 추가
            COALESCE(rml.is_matched, FALSE) as is_matched
        FROM shilla_receipts sr
        LEFT JOIN shilla_excel_data se ON REPLACE(se."receiptNumber"::text, '.0', '') = sr.receipt_number AND se.user_id = :user_id
        LEFT JOIN receipt_match_log rml ON rml.receipt_number = sr.receipt_number 
                                        AND rml.user_id = :user_id
                                        AND rml.duty_free_type = 'shilla'
        LEFT JOIN passports p ON (sr.passport_number = p.passport_number OR COALESCE(se.passport_number, rml.passport_number) = p.passport_number) 
                               AND p.user_id = :user_id
        WHERE sr.user_id = :user_id
        ORDER BY order_name, sr.receipt_number
        """
        all_receipts = db.execute(text(all_receipts_sql), {"user_id": user_id}).fetchall()
        
        # 결과를 매칭/미매칭으로 분리
        matched = []
        unmatched = []
        
        for row in all_receipts:
            # Row 객체에 id 속성 추가 (템플릿 호환성을 위해)
            row_dict = dict(row._mapping)  # Row를 dict로 변환
            row_dict['id'] = row_dict['receipt_id']  # id 속성 추가
            
            # SimpleNamespace로 변환하여 점 표기법 사용 가능하게 함
            from types import SimpleNamespace
            row_obj = SimpleNamespace(**row_dict)
            
            print(f"🔍 처리 중인 영수증: {row_obj.receipt_number}, is_matched: {row_obj.is_matched}, excel_name: {row_obj.excel_name}")
            
            if row_obj.is_matched:  # receipt_match_log.is_matched가 True인 경우
                matched.append(row_obj)
                print(f"  ✅ 매칭됨으로 분류: {row_obj.receipt_number}")
            else:  # receipt_match_log.is_matched가 False이거나 NULL인 경우
                unmatched.append(row_obj)
                print(f"  ❌ 미매칭으로 분류: {row_obj.receipt_number}")
        
        print(f"신라 조회 결과: 전체 {len(all_receipts)}개, 매칭됨 {len(matched)}개, 미매칭 {len(unmatched)}개")
        
        # 디버깅: 각 영수증의 매칭 상태 출력
        for row in all_receipts:
            print(f"  영수증: {row.receipt_number}, 매칭: {row.is_matched}, 엑셀이름: {row.excel_name}")
            
        # unmatched 항목들의 id 확인
        print(f"매칭되지 않은 영수증 ID들: {[item.id for item in unmatched]}")
        
        # 매칭된 결과를 고객별로 그룹화 (상세 정보 포함)
        customer_data = {}
        receipt_id_mapping = {}
        
        for row in matched:
            # SimpleNamespace 객체이므로 점 표기법으로 접근
            receipt_id = row.receipt_id
            receipt_number = row.receipt_number
            excel_name = row.excel_name
            receipt_passport_number = row.receipt_passport_number
            excel_passport_number = row.excel_passport_number
            passport_name = row.passport_name
            passport_birthday = row.passport_birthday
            passport_is_matched = row.passport_is_matched
            passport_status = row.passport_status
            order_name = row.order_name
            sales_date = row.sales_date
            category = row.category
            brand = row.brand
            product_code = row.product_code
            discount_amount_krw = row.discount_amount_krw
            sales_price_usd = row.sales_price_usd
            net_sales_krw = row.net_sales_krw
            receipt_is_matched = row.is_matched
            
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
                    match_status = '여권 정보 없음'
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