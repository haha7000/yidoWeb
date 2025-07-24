from app.models.models import Receipt, ReceiptMatchLog, User, DutyFreeType, ShillaReceipt, Passport
from app.core.database import SessionLocal
from app.utils.helpers import safe_float
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from decimal import Decimal

def matchingResult(user_id):
    """롯데 면세점 매칭 로직 - 영수증 단위로 매칭 로그 생성 (중복 방지)"""
    # 영수증 단위로 매칭 결과 조회 및 상품 정보 집계
    sql = """
    SELECT 
        unique_receipts.receipt_number,
        BOOL_OR(e."receiptNumber" IS NOT NULL) AS is_matched,
        MAX(e.name) as excel_name,
        MAX(p.passport_number) as passport_number,
        MAX(p.birthday) as birthday,
        -- 집계된 상품 정보
        MIN(e."매출일자") as sales_date,
        STRING_AGG(DISTINCT e."카테고리", ', ') as categories,
        STRING_AGG(DISTINCT e."브랜드", ', ') as brands,
        COUNT(e."상품코드") as product_count,
        SUM(CASE 
            WHEN e."할인액(\)" IS NOT NULL AND e."할인액(\)" != 0
            THEN e."할인액(\)"
            ELSE 0
        END) as total_discount_krw,
        SUM(CASE 
            WHEN e."판매가($)" IS NOT NULL AND e."판매가($)" != 0
            THEN e."판매가($)"
            ELSE 0
        END) as total_sales_usd,
        SUM(CASE 
            WHEN e."순매출액(\)" IS NOT NULL AND e."순매출액(\)" != 0
            THEN e."순매출액(\)"
            ELSE 0
        END) as total_net_sales_krw,
        MIN(e."점구분") as store_branch
    FROM (
        SELECT DISTINCT receipt_number 
        FROM receipts 
        WHERE user_id = :user_id 
          AND receipt_number IS NOT NULL
    ) unique_receipts
    LEFT JOIN lotte_excel_data e ON unique_receipts.receipt_number = e."receiptNumber"
    LEFT JOIN passports p ON e.name = p.name AND p.user_id = :user_id
    GROUP BY unique_receipts.receipt_number
    ORDER BY unique_receipts.receipt_number
    """

    with SessionLocal() as session:
        results = session.execute(text(sql), {"user_id": user_id}).fetchall()
        print(f"롯데 매칭 처리할 영수증: {len(results)}개")

        # 1단계: 중복 로그 정리 후 기존 로그 조회
        existing_logs_query = session.query(ReceiptMatchLog).filter(
            ReceiptMatchLog.user_id == user_id,
            ReceiptMatchLog.duty_free_type == "lotte"
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
        
        print(f"기존 롯데 매칭 로그: {len(existing_logs)}개 (중복 제거 후)")

        # 2단계: 영수증 단위 매칭 로그 업데이트/생성 (선택적 처리)
        processed_receipts = set()
        
        for row in results:
            (receipt_number, is_matched, excel_name, passport_number, birthday,
             sales_date, categories, brands, product_count, total_discount_krw,
             total_sales_usd, total_net_sales_krw, store_branch) = row

            print(f"롯데 영수증: {receipt_number}, 매칭: {is_matched}, 최종 이름: {excel_name}")
            if is_matched:
                print(f"  - 매출일자: {sales_date}")
                print(f"  - 카테고리: {categories}")
                print(f"  - 브랜드: {brands}")
                print(f"  - 상품 수: {product_count}")
                print(f"  - 총 할인액(원): {total_discount_krw}")
                print(f"  - 총 판매가($): {total_sales_usd}")
                print(f"  - 총 순매출액(원): {total_net_sales_krw}")
                print(f"  - 점구분: {store_branch}")
            
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
            
            # 기존 로그가 있으면 업데이트, 없으면 새로 생성
            if receipt_number in existing_logs:
                # 기존 로그 업데이트
                match_log = existing_logs[receipt_number]
                match_log.is_matched = is_matched
                match_log.excel_name = excel_name
                match_log.passport_number = passport_number
                match_log.birthday = birthday
                match_log.sales_date = parsed_sales_date
                match_log.category = categories
                match_log.brand = brands
                match_log.product_code = f"TOTAL_{product_count}_ITEMS"
                match_log.discount_amount_krw = safe_float(total_discount_krw)
                match_log.sales_price_usd = safe_float(total_sales_usd)
                match_log.net_sales_krw = safe_float(total_net_sales_krw)
                match_log.store_branch = store_branch
                match_log.checked_at = datetime.now()  # 업데이트 시간 갱신
                print(f"기존 매칭 로그 업데이트: {receipt_number}")
            else:
                # 새 매칭 로그 생성
                match_log = ReceiptMatchLog(
                    user_id=user_id,
                    receipt_number=receipt_number,
                    is_matched=is_matched,
                    excel_name=excel_name,
                    passport_number=passport_number,
                    birthday=birthday,
                    sales_date=parsed_sales_date,
                    category=categories,
                    brand=brands,
                    product_code=f"TOTAL_{product_count}_ITEMS",
                    discount_amount_krw=safe_float(total_discount_krw),
                    sales_price_usd=safe_float(total_sales_usd),
                    net_sales_krw=safe_float(total_net_sales_krw),
                    store_branch=store_branch,
                    duty_free_type="lotte"
                )
                session.add(match_log)
                print(f"새 매칭 로그 생성: {receipt_number}")
            
            processed_receipts.add(receipt_number)
                
            print(f"영수증 단위 매칭 로그 처리: {receipt_number} ({product_count}개 상품)")

        # 3단계: 더 이상 존재하지 않는 영수증의 로그 정리 (선택적 삭제)
        obsolete_receipts = set(existing_logs.keys()) - processed_receipts
        if obsolete_receipts:
            print(f"더 이상 존재하지 않는 영수증 로그 {len(obsolete_receipts)}개 정리 중...")
            for obsolete_receipt in obsolete_receipts:
                session.delete(existing_logs[obsolete_receipt])
                print(f"  - 삭제: {obsolete_receipt}")

        session.commit()
        print(f"✅ 롯데 매칭 로직 완료:")
        print(f"  - 처리된 영수증: {len(processed_receipts)}개")
        print(f"  - 업데이트된 로그: {len([r for r in processed_receipts if r in existing_logs])}개") 
        print(f"  - 새로 생성된 로그: {len([r for r in processed_receipts if r not in existing_logs])}개")
        print(f"  - 정리된 obsolete 로그: {len(obsolete_receipts)}개")

        # 4단계: 여권 매칭 상태 업데이트
        passport_update_sql = """
        UPDATE passports p
        SET is_matched = TRUE
        FROM lotte_excel_data e
        WHERE p.name = e.name 
        AND p.user_id = :user_id
        AND e."receiptNumber" IN (
            SELECT rml.receipt_number 
            FROM receipt_match_log rml
            WHERE rml.user_id = :user_id AND rml.is_matched = TRUE AND rml.duty_free_type = 'lotte'
        )
        """
        updated_passports = session.execute(text(passport_update_sql), {"user_id": user_id}).rowcount
        print(f"여권 매칭 상태 업데이트: {updated_passports}개")

        session.commit()
        print("롯데 매칭 결과 저장 완료")

def fetch_results(user_id, duty_free_type="lotte"):
    """면세점 타입에 따라 적절한 결과 반환"""
    with SessionLocal() as db:
        if duty_free_type == "shilla":
            # 신라 면세점 결과 조회
            from app.services.shilla_matching import fetch_shilla_results_with_details
            return fetch_shilla_results_with_details(user_id)
        else:
            # 롯데 면세점 결과 조회
            # 사용자별 매칭된 영수증 번호 조회
            matched_sql = """
            SELECT DISTINCT r.*
            FROM receipts r
            JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number
            WHERE rml.is_matched = TRUE AND r.user_id = :user_id AND rml.user_id = :user_id
            """
            matched = db.execute(text(matched_sql), {"user_id": user_id}).fetchall()

            # 사용자별 매칭되지 않은 영수증 번호 조회 (receipt_number가 None인 경우도 포함)
            unmatched_sql = """
            SELECT DISTINCT r.*
            FROM receipts r
            LEFT JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number AND rml.user_id = r.user_id
            WHERE r.user_id = :user_id
            AND (
                r.receipt_number IS NULL OR
                (rml.is_matched = FALSE AND rml.user_id = :user_id)
            )
            """
            unmatched = db.execute(text(unmatched_sql), {"user_id": user_id}).fetchall()

            return matched, unmatched