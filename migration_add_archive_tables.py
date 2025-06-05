# migration_add_archive_tables.py
from app.core.database import my_engine
from app.models.models import Base
from sqlalchemy import text

print("📦 아카이브 테이블 추가 마이그레이션 시작...")

with my_engine.connect() as conn:
    try:
        # 트랜잭션 시작
        conn.execute(text("BEGIN"))
        
        print("✅ 1단계: 아카이브 테이블 생성")
        
        # 1. processing_archives 테이블 생성
        create_archives_table = """
        CREATE TABLE IF NOT EXISTS processing_archives (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            session_name VARCHAR(200) NOT NULL,
            archive_date TIMESTAMP DEFAULT NOW(),
            total_receipts INTEGER DEFAULT 0,
            matched_receipts INTEGER DEFAULT 0,
            total_passports INTEGER DEFAULT 0,
            matched_passports INTEGER DEFAULT 0,
            duty_free_type VARCHAR(20),
            notes TEXT,
            archive_data JSONB
        );
        """
        conn.execute(text(create_archives_table))
        print("   ✅ processing_archives 테이블 생성 완료")
        
        # 2. matching_history 테이블 생성
        create_history_table = """
        CREATE TABLE IF NOT EXISTS matching_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            archive_id INTEGER REFERENCES processing_archives(id) ON DELETE SET NULL,
            customer_name VARCHAR(100),
            passport_number VARCHAR(20),
            receipt_numbers TEXT,
            excel_data JSONB,
            match_status VARCHAR(50),
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
        conn.execute(text(create_history_table))
        print("   ✅ matching_history 테이블 생성 완료")
        
        print("✅ 2단계: 인덱스 생성")
        
        # 3. 성능을 위한 인덱스 생성
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_archives_user_date ON processing_archives(user_id, archive_date DESC);",
            "CREATE INDEX IF NOT EXISTS idx_history_user_customer ON matching_history(user_id, customer_name);",
            "CREATE INDEX IF NOT EXISTS idx_history_passport ON matching_history(passport_number);",
            "CREATE INDEX IF NOT EXISTS idx_history_archive ON matching_history(archive_id);",
            "CREATE INDEX IF NOT EXISTS idx_history_created_at ON matching_history(created_at DESC);"
        ]
        
        for idx_sql in indexes:
            conn.execute(text(idx_sql))
            
        print("   ✅ 인덱스 생성 완료")
        
        # PostgreSQL 전문 검색 인덱스 (선택사항)
        try:
            print("✅ 3단계: 전문 검색 인덱스 생성 (PostgreSQL)")
            gin_index = """
            CREATE INDEX IF NOT EXISTS idx_history_receipt_search 
            ON matching_history USING gin(to_tsvector('simple', receipt_numbers));
            """
            conn.execute(text(gin_index))
            print("   ✅ 전문 검색 인덱스 생성 완료")
        except Exception as e:
            print(f"   ⚠️ 전문 검색 인덱스 생성 실패 (PostgreSQL 아닐 수 있음): {e}")
        
        # 커밋
        conn.execute(text("COMMIT"))
        print("✅ 마이그레이션 커밋 완료")
        
    except Exception as e:
        # 롤백
        conn.execute(text("ROLLBACK"))
        print(f"❌ 마이그레이션 실패, 롤백됨: {e}")
        raise e

print("📦 아카이브 테이블 추가 마이그레이션 완료!")
print("💡 이제 처리 완료 후 이력 저장 및 데이터 초기화 기능을 사용할 수 있습니다.")
print("💡 새로운 기능:")
print("   - 처리 완료 버튼으로 세션 종료 및 초기화")
print("   - 이력 조회 페이지에서 과거 처리 결과 검색")
print("   - 사용자별 완전한 데이터 격리")