# migration_add_simple_columns.py
from app.core.database import my_engine
from sqlalchemy import text

print("📦 receipt_match_log 테이블에 간단한 컬럼들만 추가...")

with my_engine.connect() as conn:
    try:
        # 트랜잭션 시작
        conn.execute(text("BEGIN"))
        
        print("✅ 기존 additional_data 컬럼 제거 (있다면)")
        try:
            conn.execute(text("ALTER TABLE receipt_match_log DROP COLUMN IF EXISTS additional_data"))
            print("   ✅ additional_data 컬럼 제거 완료")
        except Exception as e:
            print(f"   ⚠️ additional_data 컬럼 제거 중 오류: {e}")
        
        print("✅ 기존 컬럼들이 있는지 확인 후 누락된 것만 추가")
        
        # 컬럼 존재 여부 확인 쿼리들
        check_columns = [
            ("sales_date", "ALTER TABLE receipt_match_log ADD COLUMN sales_date DATE"),
            ("category", "ALTER TABLE receipt_match_log ADD COLUMN category VARCHAR(100)"),
            ("brand", "ALTER TABLE receipt_match_log ADD COLUMN brand VARCHAR(100)"),
            ("product_code", "ALTER TABLE receipt_match_log ADD COLUMN product_code VARCHAR(50)"),
            ("discount_amount_krw", "ALTER TABLE receipt_match_log ADD COLUMN discount_amount_krw FLOAT"),
            ("sales_price_usd", "ALTER TABLE receipt_match_log ADD COLUMN sales_price_usd FLOAT"),
            ("net_sales_krw", "ALTER TABLE receipt_match_log ADD COLUMN net_sales_krw FLOAT")
        ]
        
        for col_name, add_sql in check_columns:
            try:
                # 컬럼 존재 확인
                check_sql = """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'receipt_match_log' AND column_name = :col_name
                """
                exists = conn.execute(text(check_sql), {"col_name": col_name}).fetchone()
                
                if not exists:
                    conn.execute(text(add_sql))
                    print(f"   ✅ {col_name} 컬럼 추가 완료")
                else:
                    print(f"   ✅ {col_name} 컬럼 이미 존재")
                    
            except Exception as e:
                print(f"   ⚠️ {col_name} 컬럼 처리 중 오류: {e}")
        
        # 커밋
        conn.execute(text("COMMIT"))
        print("✅ 마이그레이션 커밋 완료")
        
    except Exception as e:
        # 롤백
        conn.execute(text("ROLLBACK"))
        print(f"❌ 마이그레이션 실패, 롤백됨: {e}")
        raise e

print("📦 간단한 컬럼 추가 마이그레이션 완료!")
print("💡 추가된 컬럼들:")
print("   - sales_date: 매출일자")
print("   - category: 카테고리")
print("   - brand: 브랜드")
print("   - product_code: 상품코드")
print("   - discount_amount_krw: 할인액(원)")
print("   - sales_price_usd: 판매가(달러)")
print("   - net_sales_krw: 순매출액(원)")