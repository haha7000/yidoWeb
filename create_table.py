# # create_tables.py
# from app.core.database import my_engine
# from app.models.models import Base


# Base.metadata.drop_all(bind=my_engine)     # 테이블 모두 삭제
# Base.metadata.create_all(bind=my_engine)   # 테이블 새로 생성
# print("📦 테이블 초기화 및 재생성 완료!")

# create_tables.py 안전한 버전
from app.core.database import my_engine
from app.models.models import Base
from sqlalchemy import text

print("📦 데이터베이스 테이블 초기화 시작...")

# 1. 개별 테이블 삭제 (순서 중요)
with my_engine.connect() as conn:
    try:
        # 외래키가 있는 테이블부터 먼저 삭제
        tables_to_drop = [
            "passport_matches",
            "receipt_match_log", 
            "unrecognized_images",
            "receipts",
            "passports", 
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

# 2. 새 테이블들 생성
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