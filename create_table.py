# create_tables.py 안전한 버전
from app.core.database import my_engine
from app.models.models import Base
from sqlalchemy import text

print("📦 데이터베이스 테이블 초기화 시작...")

# 1. 개별 테이블 삭제 (순서 중요 - 외래키 관계 고려)
with my_engine.connect() as conn:
    try:
        # 외래키가 있는 테이블부터 먼저 삭제
        tables_to_drop = [
            "receipt_match_log", 
            "unrecognized_images",
            "receipts",
            "passports", 
            "shilla_receipts",
            "lotte_excel_data",    # 동적 테이블
            "shilla_excel_data",   # 동적 테이블
            "excel_data",          # 기존 테이블
            "users"
        ]
        
        for table in tables_to_drop:
            try:
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE;"))
                print(f"✅ {table} 테이블 삭제 완료")
            except Exception as e:
                print(f"⚠️ {table} 테이블 삭제 중 오류 (무시): {e}")
        
        conn.commit()
        print("✅ 기존 테이블 삭제 완료")
        
    except Exception as e:
        print(f"❌ 테이블 삭제 중 오류: {e}")

# 2. 새 테이블들 생성 (models.py의 Base 기반)
try:
    Base.metadata.create_all(bind=my_engine)
    print("✅ 새 테이블 생성 완료")
    
    # 생성된 테이블 확인
    with my_engine.connect() as conn:
        result = conn.execute(text("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            ORDER BY tablename;
        """))
        tables = [row[0] for row in result]
        print(f"📋 생성된 테이블 목록: {', '.join(tables)}")
        
except Exception as e:
    print(f"❌ 테이블 생성 중 오류: {e}")

print("📦 테이블 초기화 및 재생성 완료!")
print("💡 엑셀 데이터 테이블(lotte_excel_data, shilla_excel_data)은 업로드 시 동적으로 생성됩니다.")