# migration_add_receipt_details.py
from app.core.database import my_engine
from sqlalchemy import text

print("📦 receipt_match_log 테이블에 매출 상세 정보 컬럼 추가 마이그레이션 시작...")

with my_engine.connect() as conn:
    try:
        # 트랜잭션 시작
        conn.execute(text("BEGIN"))
        
        print("✅ receipt_match_log 테이블에 새 컬럼들 추가")
        
        # 새 컬럼들 추가
        add_columns_sql = """
        ALTER TABLE receipt_match_log 
        ADD COLUMN IF NOT EXISTS sales_date DATE,
        ADD COLUMN IF NOT EXISTS category VARCHAR(100),
        ADD COLUMN IF NOT EXISTS brand VARCHAR(100),
        ADD COLUMN IF NOT EXISTS product_code VARCHAR(50),
        ADD COLUMN IF NOT EXISTS discount_amount_krw DECIMAL(12,2),
        ADD COLUMN IF NOT EXISTS sales_price_usd DECIMAL(12,2),
        ADD COLUMN IF NOT EXISTS net_sales_krw DECIMAL(12,2),
        ADD COLUMN IF NOT EXISTS additional_data JSONB;
        """
        
        conn.execute(text(add_columns_sql))
        print("   ✅ 새 컬럼들 추가 완료")
        
        # 인덱스 추가 (검색 성능 향상을 위해)
        indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_receipt_match_log_sales_date ON receipt_match_log(sales_date);",
            "CREATE INDEX IF NOT EXISTS idx_receipt_match_log_category ON receipt_match_log(category);",
            "CREATE INDEX IF NOT EXISTS idx_receipt_match_log_brand ON receipt_match_log(brand);",
            "CREATE INDEX IF NOT EXISTS idx_receipt_match_log_product_code ON receipt_match_log(product_code);"
        ]
        
        for idx_sql in indexes_sql:
            conn.execute(text(idx_sql))
        
        print("   ✅ 인덱스 추가 완료")
        
        # 커밋
        conn.execute(text("COMMIT"))
        print("✅ 마이그레이션 커밋 완료")
        
    except Exception as e:
        # 롤백
        conn.execute(text("ROLLBACK"))
        print(f"❌ 마이그레이션 실패, 롤백됨: {e}")
        raise e

print("📦 receipt_match_log 테이블 컬럼 추가 마이그레이션 완료!")
print("💡 추가된 컬럼들:")
print("   - sales_date: 매출일자")
print("   - category: 카테고리")
print("   - brand: 브랜드")
print("   - product_code: 상품코드")
print("   - discount_amount_krw: 할인액(원)")
print("   - sales_price_usd: 판매가(달러)")
print("   - net_sales_krw: 순매출액(원)")
print("   - additional_data: 추가 데이터 (JSON 형태)")