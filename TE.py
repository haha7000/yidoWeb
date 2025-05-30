# add_passport_number_to_shilla.py
from app.core.database import my_engine
from sqlalchemy import text

print("📦 신라 엑셀 데이터 테이블에 passport_number 컬럼 추가 시작...")

with my_engine.connect() as conn:
    try:
        # shilla_excel_data 테이블에 passport_number 컬럼 추가
        conn.execute(text("""
            ALTER TABLE shilla_excel_data 
            ADD COLUMN IF NOT EXISTS passport_number VARCHAR(20);
        """))
        print("✅ shilla_excel_data 테이블에 passport_number 컬럼 추가 완료")
        
        conn.commit()
        
    except Exception as e:
        print(f"❌ 마이그레이션 중 오류 발생: {e}")
        conn.rollback()

print("📦 신라 테이블 마이그레이션 완료!")