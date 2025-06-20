from app.models.models import Receipt, ReceiptMatchLog, User, DutyFreeType, ShillaReceipt
from app.core.database import SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from decimal import Decimal

def matchingResult(user_id):
    """롯데 면세점 매칭 로직 - 상품별 저장 및 수수료 합계 계산"""
    # 모든 상품별 매칭 결과 조회 (중복 허용 - 각 상품별로 개별 레코드)
    sql = """
    SELECT 
        r.receipt_number,
        CASE
            WHEN e."receiptNumber" IS NOT NULL THEN TRUE
            ELSE FALSE 
        END AS is_matched,
        e.name as excel_name,
        p.passport_number,
        p.birthday,
        -- 롯데 상품별 상세 정보
        e."매출일자" as sales_date,
        e."카테고리" as category,
        e."브랜드" as brand,
        e."상품코드" as product_code,
        e."할인액(\)" as discount_amount_krw,
        e."판매가($)" as sales_price_usd,
        e."순매출액(\)" as net_sales_krw,
        e."점구분" as store_branch
    FROM receipts r
    LEFT JOIN lotte_excel_data e ON r.receipt_number = e."receiptNumber"
    LEFT JOIN passports p ON e.name = p.name AND p.user_id = :user_id
    WHERE r.user_id = :user_id
    ORDER BY r.receipt_number, e."상품코드"
    """

    with SessionLocal() as session:
        results = session.execute(text(sql), {"user_id": user_id}).fetchall()
        print(f"롯데 매칭 처리할 상품: {len(results)}개")

        # 1단계: 기존 매칭 로그 삭제 (새로운 상품별 로그로 대체)
        session.query(ReceiptMatchLog).filter(
            ReceiptMatchLog.user_id == user_id,
            ReceiptMatchLog.duty_free_type == "lotte"
        ).delete()

        # 2단계: 상품별 매칭 로그 생성
        
        for row in results:
            (receipt_number, is_matched, excel_name, passport_number, birthday,
             sales_date, category, brand, product_code, discount_amount_krw,
             sales_price_usd, net_sales_krw, store_branch) = row
            
            print(f"롯데 상품: {receipt_number}-{product_code}, 매칭: {is_matched}, 이름: {excel_name}")
            if is_matched:
                print(f"  - 매출일자: {sales_date}")
                print(f"  - 카테고리: {category}")
                print(f"  - 브랜드: {brand}")
                print(f"  - 상품코드: {product_code}")
                print(f"  - 할인액(원): {discount_amount_krw}")
                print(f"  - 판매가($): {sales_price_usd}")
                print(f"  - 순매출액(원): {net_sales_krw}")
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
            
            # 숫자 변환 처리 함수
            def safe_float(value):
                if value is None:
                    return None
                try:
                    if isinstance(value, str):
                        # 쉼표, 통화기호, 백슬래시 제거 후 변환
                        value = value.replace(',', '').replace('￦', '').replace('$', '').replace('\\', '').strip()
                    return float(value) if value != '' else None
                except (ValueError, TypeError, AttributeError):
                    return None
            
            # 상품별 매칭 로그 생성 (매칭된 경우에만)
            if is_matched and product_code:
                match_log = ReceiptMatchLog(
                    user_id=user_id,
                    receipt_number=receipt_number,
                    is_matched=is_matched,
                    excel_name=excel_name,
                    passport_number=passport_number,
                    birthday=birthday,
                    # 상세 정보
                    sales_date=parsed_sales_date,
                    category=category,
                    brand=brand,
                    product_code=product_code,
                    discount_amount_krw=safe_float(discount_amount_krw),
                    sales_price_usd=safe_float(sales_price_usd),
                    net_sales_krw=safe_float(net_sales_krw),
                    store_branch=store_branch,
                    duty_free_type="lotte"
                )
                session.add(match_log)
                
                print(f"상품별 매칭 로그 생성: {receipt_number}-{product_code}")
            
            # 매칭되지 않은 영수증도 로그 생성 (상품 정보 없이)
            elif not is_matched:
                existing_unmatched = session.query(ReceiptMatchLog).filter(
                    ReceiptMatchLog.receipt_number == receipt_number,
                    ReceiptMatchLog.user_id == user_id,
                    ReceiptMatchLog.duty_free_type == "lotte",
                    ReceiptMatchLog.is_matched == False
                ).first()
                
                if not existing_unmatched:
                    match_log = ReceiptMatchLog(
                        user_id=user_id,
                        receipt_number=receipt_number,
                        is_matched=False,
                        excel_name=None,
                        passport_number=None,
                        birthday=None,
                        duty_free_type="lotte"
                    )
                    session.add(match_log)
                    print(f"매칭되지 않은 영수증 로그 생성: {receipt_number}")

        session.commit()
        print("롯데 상품별 매칭 결과 저장 완료")

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
            from app.services.shilla_matching import fetch_shilla_results_with_receipt_ids
            return fetch_shilla_results_with_receipt_ids(user_id)
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

            # 사용자별 매칭되지 않은 영수증 번호 조회
            unmatched_sql = """
            SELECT DISTINCT r.*
            FROM receipts r
            JOIN receipt_match_log rml ON r.receipt_number = rml.receipt_number
            WHERE rml.is_matched = FALSE AND r.user_id = :user_id AND rml.user_id = :user_id
            """
            unmatched = db.execute(text(unmatched_sql), {"user_id": user_id}).fetchall()

            return matched, unmatched