# test_commission.py - 실제 롯데 데이터 기반 수수료 계산 테스트

from app.core.database import SessionLocal
from sqlalchemy import text
from datetime import date
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

def create_fee_tables():
    """수수료 관련 테이블 생성"""
    print("🔧 수수료 테이블 생성 중...")
    
    with SessionLocal() as session:
        # 기존 테이블 삭제 (순서 중요)
        session.execute(text("DROP TABLE IF EXISTS exempt_brands CASCADE"))
        session.execute(text("DROP TABLE IF EXISTS item_fees CASCADE"))
        session.execute(text("DROP TABLE IF EXISTS brand_fees CASCADE"))
        session.execute(text("DROP TABLE IF EXISTS category_fees CASCADE"))
        session.execute(text("DROP TABLE IF EXISTS fee_settings CASCADE"))
        
        # fee_settings 테이블 생성
        session.execute(text("""
            CREATE TABLE fee_settings (
                id SERIAL PRIMARY KEY,
                company_name VARCHAR(100) NOT NULL,
                branch_name VARCHAR(100) NOT NULL,
                note TEXT,
                free_rate_threshold DECIMAL(5,4) DEFAULT 0.3000,
                effective_from DATE NOT NULL,
                effective_to DATE NOT NULL,
                creator_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # category_fees 테이블 생성
        session.execute(text("""
            CREATE TABLE category_fees (
                id SERIAL PRIMARY KEY,
                settings_id INTEGER NOT NULL,
                fee_type VARCHAR(100) NOT NULL,
                commission_rate DECIMAL(5,4) NOT NULL,
                creator_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (settings_id) REFERENCES fee_settings(id) ON DELETE CASCADE
            )
        """))
        
        # brand_fees 테이블 생성
        session.execute(text("""
            CREATE TABLE brand_fees (
                id SERIAL PRIMARY KEY,
                settings_id INTEGER NOT NULL,
                category VARCHAR(100) NOT NULL,
                brand VARCHAR(100) NOT NULL,
                commission_rate DECIMAL(5,4) NOT NULL,
                creator_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (settings_id) REFERENCES fee_settings(id) ON DELETE CASCADE
            )
        """))
        
        # item_fees 테이블 생성
        session.execute(text("""
            CREATE TABLE item_fees (
                id SERIAL PRIMARY KEY,
                settings_id INTEGER NOT NULL,
                category VARCHAR(100) NOT NULL,
                brand VARCHAR(100) NOT NULL,
                product_code VARCHAR(50) NOT NULL,
                commission_rate DECIMAL(5,4) NOT NULL,
                creator_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (settings_id) REFERENCES fee_settings(id) ON DELETE CASCADE
            )
        """))
        
        # exempt_brands 테이블 생성
        session.execute(text("""
            CREATE TABLE exempt_brands (
                id SERIAL PRIMARY KEY,
                settings_id INTEGER NOT NULL,
                category VARCHAR(100) NOT NULL,
                import_type VARCHAR(50) NOT NULL,
                brand VARCHAR(100) NOT NULL,
                creator_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (settings_id) REFERENCES fee_settings(id) ON DELETE CASCADE
            )
        """))
        
        session.commit()
        print("✅ 수수료 테이블 생성 완료")

def insert_sample_fee_data():
    """실제 롯데 데이터 기반 샘플 수수료 데이터 삽입"""
    print("📊 실제 데이터 기반 샘플 수수료 데이터 삽입 중...")
    
    with SessionLocal() as session:
        # 기존 데이터 삭제
        session.execute(text("DELETE FROM exempt_brands"))
        session.execute(text("DELETE FROM item_fees"))
        session.execute(text("DELETE FROM brand_fees"))
        session.execute(text("DELETE FROM category_fees"))
        session.execute(text("DELETE FROM fee_settings"))
        
        # 1. fee_settings 삽입
        session.execute(text("""
            INSERT INTO fee_settings (company_name, branch_name, note, free_rate_threshold, effective_from, effective_to, creator_id)
            VALUES ('LOTTE', '명동본점', '롯데면세점 명동본점 수수료 기준', 0.3000, '2024-01-01', '2024-12-31', 1)
        """))
        
        # settings_id 가져오기
        result = session.execute(text("SELECT id FROM fee_settings WHERE company_name = 'LOTTE' AND branch_name = '명동본점'")).first()
        settings_id = result[0]
        
        # 2. category_fees 삽입 (실제 롯데 카테고리 기반)
        category_data = [
            ('FASHION', 0.1200),        # 12.0% - 패션 카테고리
            ('COSMETICS', 0.2500),      # 25.0% - 화장품 카테고리
            ('PERFUME', 0.2200),        # 22.0% - 향수 카테고리
            ('LIQUOR', 0.0700),         # 7.0% - 주류 카테고리
            ('TOBACCO', 0.0700),        # 7.0% - 담배 카테고리
            ('FOOD', 0.0800),           # 8.0% - 식품 카테고리
            ('ELECTRONICS', 0.0600),    # 6.0% - 전자기기 카테고리
        ]
        
        for fee_type, commission_rate in category_data:
            session.execute(text("""
                INSERT INTO category_fees (settings_id, fee_type, commission_rate, creator_id)
                VALUES (:settings_id, :fee_type, :commission_rate, 1)
            """), {
                "settings_id": settings_id,
                "fee_type": fee_type,
                "commission_rate": commission_rate
            })
        
        # 3. brand_fees 삽입 (실제 롯데 브랜드 기반)
        brand_data = [
            ('FASHION', 'CELINE', 0.1500),      # 15.0% - 셀린느 특별 수수료
            ('FASHION', 'LOUIS VUITTON', 0.1000), # 10.0% - 루이비통 특별 수수료
            ('FASHION', 'LOEWE', 0.1300),       # 13.0% - 로에베 특별 수수료
        ]
        
        for category, brand, commission_rate in brand_data:
            session.execute(text("""
                INSERT INTO brand_fees (settings_id, category, brand, commission_rate, creator_id)
                VALUES (:settings_id, :category, :brand, :commission_rate, 1)
            """), {
                "settings_id": settings_id,
                "category": category,
                "brand": brand,
                "commission_rate": commission_rate
            })
        
        # 4. item_fees 삽입 (실제 롯데 상품코드 기반)
        item_data = [
            ('FASHION', 'CELINE', '2073450195', 0.0800),  # 8.0% - 셀린느 지갑 특별 수수료
            ('FASHION', 'CELINE', '2073450153', 0.0500),  # 5.0% - 셀린느 가방 특별 수수료
            ('FASHION', 'LOEWE', '2073426759', 0.0900),   # 9.0% - 로에베 토트백 특별 수수료
        ]
        
        for category, brand, product_code, commission_rate in item_data:
            session.execute(text("""
                INSERT INTO item_fees (settings_id, category, brand, product_code, commission_rate, creator_id)
                VALUES (:settings_id, :category, :brand, :product_code, :commission_rate, 1)
            """), {
                "settings_id": settings_id,
                "category": category,
                "brand": brand,
                "product_code": product_code,
                "commission_rate": commission_rate
            })
        
        # 5. exempt_brands 삽입 (수수료 제외 브랜드)
        exempt_data = [
            ('FASHION', '수입', 'HERMÈS'),  # 에르메스는 수수료 제외
        ]
        
        for category, import_type, brand in exempt_data:
            session.execute(text("""
                INSERT INTO exempt_brands (settings_id, category, import_type, brand, creator_id)
                VALUES (:settings_id, :category, :import_type, :brand, 1)
            """), {
                "settings_id": settings_id,
                "category": category,
                "import_type": import_type,
                "brand": brand
            })
        
        session.commit()
        print("✅ 실제 데이터 기반 샘플 수수료 데이터 삽입 완료")

def insert_sample_receipt_data(user_id: int = 1):
    """실제 롯데 데이터 기반 샘플 영수증 데이터 삽입"""
    print("🧾 실제 데이터 기반 샘플 영수증 데이터 삽입 중...")
    
    with SessionLocal() as session:
        # 기존 데이터 삭제
        session.execute(text("DELETE FROM receipt_match_log WHERE user_id = :user_id"), {"user_id": user_id})
        
        # 실제 롯데 데이터 기반 샘플 영수증 데이터
        receipt_data = [
            # 1순위 테스트: 상품코드+브랜드+카테고리 모두 일치 (item_fees)
            {
                "user_id": user_id,
                "receipt_number": "90100424003726",  # 실제 영수증 번호
                "is_matched": True,
                "excel_name": "GUAN TIANTIAN",
                "sales_date": date(2024, 10, 1),
                "category": "FASHION",
                "brand": "CELINE",
                "product_code": "2073450195",  # item_fees에 있는 상품코드 (8% 수수료)
                "discount_amount_krw": 44866.0,  # 실제 할인액
                "sales_price_usd": 681.0,
                "net_sales_krw": 853781.0,  # 실제 순매출액
                "store_branch": "명동본점",
                "duty_free_type": "lotte"
            },
            # 2순위 테스트: 브랜드+카테고리 일치 (brand_fees)
            {
                "user_id": user_id,
                "receipt_number": "90100324003445",  # 실제 영수증 번호
                "is_matched": True,
                "excel_name": "PAN HONG",
                "sales_date": date(2024, 10, 1),
                "category": "FASHION",
                "brand": "LOUIS VUITTON",
                "product_code": "2041326668",  # item_fees에 없는 상품코드
                "discount_amount_krw": 0.0,  # 할인 없음
                "sales_price_usd": 950.0,
                "net_sales_krw": 1253620.0,
                "store_branch": "명동본점",
                "duty_free_type": "lotte"
            },
            # 3순위 테스트: 카테고리만 일치 (category_fees)
            {
                "user_id": user_id,
                "receipt_number": "90102624005506",  # 실제 영수증 번호
                "is_matched": True,
                "excel_name": "PAN HONG",
                "sales_date": date(2024, 10, 1),
                "category": "FASHION",
                "brand": "UNKNOWN_BRAND",  # brand_fees에 없는 브랜드
                "product_code": "9999999999",  # item_fees에 없는 상품코드
                "discount_amount_krw": 125362.0,
                "sales_price_usd": 1900.0,
                "net_sales_krw": 2381878.0,
                "store_branch": "명동본점",
                "duty_free_type": "lotte"
            },
            # 할인율 임계값 테스트 (5% 할인 - 임계값 미만)
            {
                "user_id": user_id,
                "receipt_number": "90100424003732",  # 실제 영수증 번호
                "is_matched": True,
                "excel_name": "ZHANG NI",
                "sales_date": date(2024, 10, 1),
                "category": "FASHION",
                "brand": "CELINE",
                "product_code": "2073450153",  # item_fees에 있는 상품코드 (5% 수수료)
                "discount_amount_krw": 240167.0,  # 실제 할인액 (약 5% 할인)
                "sales_price_usd": 3648.0,
                "net_sales_krw": 4573734.0,
                "store_branch": "명동본점",
                "duty_free_type": "lotte"
            },
            # 수수료 제외 브랜드 테스트 (exempt_brands)
            {
                "user_id": user_id,
                "receipt_number": "TEST_HERMES_001",
                "is_matched": True,
                "excel_name": "TEST CUSTOMER",
                "sales_date": date(2024, 10, 1),
                "category": "FASHION",
                "brand": "HERMÈS",  # exempt_brands에 있는 브랜드
                "product_code": "TEST_001",
                "discount_amount_krw": 50000.0,
                "sales_price_usd": 500.0,
                "net_sales_krw": 600000.0,
                "store_branch": "명동본점",
                "duty_free_type": "lotte"
            }
        ]
        
        for data in receipt_data:
            session.execute(text("""
                INSERT INTO receipt_match_log (
                    user_id, receipt_number, is_matched, excel_name, sales_date,
                    category, brand, product_code, discount_amount_krw, sales_price_usd, net_sales_krw,
                    store_branch, duty_free_type
                ) VALUES (
                    :user_id, :receipt_number, :is_matched, :excel_name, :sales_date,
                    :category, :brand, :product_code, :discount_amount_krw, :sales_price_usd, :net_sales_krw,
                    :store_branch, :duty_free_type
                )
            """), data)
        
        session.commit()
        print("✅ 실제 데이터 기반 샘플 영수증 데이터 삽입 완료")

def calculate_commission_rate(user_id: int, category: str, brand: str, product_code: str, 
                            discount_rate: float, import_type: str = "수입") -> float:
    """수수료율 계산 함수"""
    
    with SessionLocal() as session:
        # fee_settings 조회
        settings_result = session.execute(text("""
            SELECT id, free_rate_threshold 
            FROM fee_settings 
            WHERE company_name = 'LOTTE' AND branch_name = '명동본점'
            LIMIT 1
        """)).first()
        
        if not settings_result:
            print("수수료 설정을 찾을 수 없습니다.")
            return 0.0
        
        settings_id, free_rate_threshold = settings_result
        
        # 할인율 임계값 확인 (30% 이상이면 수수료 0%)
        if discount_rate >= (float(free_rate_threshold) * 100):
            print(f"할인율 {discount_rate:.2f}%가 임계값 {float(free_rate_threshold)*100:.1f}% 이상이므로 수수료 0% 적용")
            return 0.0
        
        # 최우선순위: exempt_brands 확인
        exempt_result = session.execute(text("""
            SELECT id FROM exempt_brands 
            WHERE settings_id = :settings_id 
            AND category = :category 
            AND brand = :brand 
            AND import_type = :import_type
            LIMIT 1
        """), {
            "settings_id": settings_id,
            "category": category,
            "brand": brand,
            "import_type": import_type
        }).first()
        
        if exempt_result:
            print(f"브랜드 {brand}는 수수료 제외 브랜드입니다. 수수료 0% 적용")
            return 0.0
        
        # 1순위: item_fees 확인 (카테고리+브랜드+상품코드 모두 일치)
        item_result = session.execute(text("""
            SELECT commission_rate FROM item_fees 
            WHERE settings_id = :settings_id 
            AND category = :category 
            AND brand = :brand 
            AND product_code = :product_code
            LIMIT 1
        """), {
            "settings_id": settings_id,
            "category": category,
            "brand": brand,
            "product_code": product_code
        }).first()
        
        if item_result:
            rate = float(item_result[0])
            print(f"1순위 (item_fees): 상품코드 {product_code}, 브랜드 {brand}, 카테고리 {category} → {rate*100:.1f}% 수수료")
            return rate
        
        # 2순위: brand_fees 확인 (카테고리+브랜드 일치)
        brand_result = session.execute(text("""
            SELECT commission_rate FROM brand_fees 
            WHERE settings_id = :settings_id 
            AND category = :category 
            AND brand = :brand
            LIMIT 1
        """), {
            "settings_id": settings_id,
            "category": category,
            "brand": brand
        }).first()
        
        if brand_result:
            rate = float(brand_result[0])
            print(f"2순위 (brand_fees): 브랜드 {brand}, 카테고리 {category} → {rate*100:.1f}% 수수료")
            return rate
        
        # 3순위: category_fees 확인 (카테고리만 일치)
        category_result = session.execute(text("""
            SELECT commission_rate FROM category_fees 
            WHERE settings_id = :settings_id 
            AND fee_type = :category
            LIMIT 1
        """), {
            "settings_id": settings_id,
            "category": category
        }).first()
        
        if category_result:
            rate = float(category_result[0])
            print(f"3순위 (category_fees): 카테고리 {category} → {rate*100:.1f}% 수수료")
            return rate
        
        print(f"수수료율을 찾을 수 없습니다: 카테고리={category}, 브랜드={brand}, 상품코드={product_code}")
        return 0.0

def test_commission_calculation(user_id: int = 1):
    """수수료 계산 테스트"""
    print("🧪 실제 데이터 기반 수수료 계산 테스트 시작...")
    
    with SessionLocal() as session:
        # 테스트할 영수증 데이터 조회
        result = session.execute(text("""
            SELECT receipt_number, excel_name, category, brand, product_code, 
                   discount_amount_krw, net_sales_krw, sales_price_usd
            FROM receipt_match_log 
            WHERE user_id = :user_id AND is_matched = TRUE
            ORDER BY receipt_number
        """), {"user_id": user_id})
        
        receipts = result.fetchall()
        print(f"테스트할 영수증: {len(receipts)}개\n")
        
        for receipt in receipts:
            receipt_number, excel_name, category, brand, product_code, discount_amount_krw, net_sales_krw, sales_price_usd = receipt
            
            print(f"=== 영수증: {receipt_number} ===")
            print(f"고객명: {excel_name}")
            print(f"카테고리: {category}")
            print(f"브랜드: {brand}")
            print(f"상품코드: {product_code}")
            print(f"할인액(원): {discount_amount_krw:,.0f}")
            print(f"순매출액(원): {net_sales_krw:,.0f}")
            print(f"판매가($): {sales_price_usd}")
            
            # 할인율 계산
            total_sales_krw = net_sales_krw + discount_amount_krw
            discount_rate = (discount_amount_krw / total_sales_krw * 100) if total_sales_krw > 0 else 0.0
            print(f"할인율: {discount_rate:.2f}%")
            
            # 수수료율 계산
            commission_rate = calculate_commission_rate(
                user_id=user_id,
                category=category,
                brand=brand,
                product_code=str(product_code),
                discount_rate=discount_rate,
                import_type="수입"
            )
            
            # 수수료 계산
            commission_fee = net_sales_krw * commission_rate
            print(f"계산된 수수료: {commission_fee:,.0f}원 (수수료율: {commission_rate*100:.1f}%)")
            print("-" * 50)
        
        print("✅ 실제 데이터 기반 수수료 계산 테스트 완료")

def update_receipt_commissions(user_id: int = 1):
    """계산된 수수료를 receipt_match_log에 업데이트"""
    print("💰 계산된 수수료를 데이터베이스에 업데이트 중...")
    
    with SessionLocal() as session:
        # 매칭된 영수증 데이터 조회
        result = session.execute(text("""
            SELECT id, category, brand, product_code, discount_amount_krw, net_sales_krw
            FROM receipt_match_log 
            WHERE user_id = :user_id AND is_matched = TRUE
        """), {"user_id": user_id})
        
        receipts = result.fetchall()
        
        for receipt in receipts:
            receipt_id, category, brand, product_code, discount_amount_krw, net_sales_krw = receipt
            
            # 할인율 계산
            total_sales_krw = net_sales_krw + discount_amount_krw
            discount_rate = (discount_amount_krw / total_sales_krw * 100) if total_sales_krw > 0 else 0.0
            
            # 수수료율 계산
            commission_rate = calculate_commission_rate(
                user_id=user_id,
                category=category,
                brand=brand,
                product_code=str(product_code),
                discount_rate=discount_rate,
                import_type="수입"
            )
            
            # 수수료 계산
            commission_fee = net_sales_krw * commission_rate
            
            # 할인율과 수수료를 데이터베이스에 업데이트
            session.execute(text("""
                UPDATE receipt_match_log 
                SET discount_rate = :discount_rate, commission_fee = :commission_fee
                WHERE id = :receipt_id
            """), {
                "discount_rate": Decimal(str(round(discount_rate, 2))),
                "commission_fee": Decimal(str(round(commission_fee, 2))),
                "receipt_id": receipt_id
            })
        
        session.commit()
        print("✅ 수수료 업데이트 완료")

def show_final_results(user_id: int = 1):
    """최종 결과 표시"""
    print("📋 최종 수수료 계산 결과:")
    
    with SessionLocal() as session:
        result = session.execute(text("""
            SELECT receipt_number, excel_name, category, brand, product_code,
                   net_sales_krw, discount_rate, commission_fee
            FROM receipt_match_log 
            WHERE user_id = :user_id AND is_matched = TRUE
            ORDER BY receipt_number
        """), {"user_id": user_id})
        
        receipts = result.fetchall()
        total_commission = 0
        
        print("\n" + "="*80)
        print(f"{'영수증번호':<15} {'고객명':<12} {'브랜드':<15} {'순매출액(원)':<12} {'할인율':<8} {'수수료(원)':<10}")
        print("="*80)
        
        for receipt in receipts:
            receipt_number, excel_name, category, brand, product_code, net_sales_krw, discount_rate, commission_fee = receipt
            total_commission += float(commission_fee or 0)
            
            print(f"{receipt_number:<15} {excel_name:<12} {brand:<15} {net_sales_krw:>10,.0f} {discount_rate or 0:>6.1f}% {commission_fee or 0:>8,.0f}")
        
        print("="*80)
        print(f"{'총 수수료:':<65} {total_commission:>8,.0f}원")
        print("="*80)

if __name__ == "__main__":
    # 테스트 실행
    create_fee_tables()
    insert_sample_fee_data()
    insert_sample_receipt_data(user_id=1)  # user_id = 1로 테스트
    test_commission_calculation(user_id=1)
    update_receipt_commissions(user_id=1)
    show_final_results(user_id=1)
 