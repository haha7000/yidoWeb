# migration_add_duty_free.py
from app.core.database import my_engine
from app.models.models import Base
from sqlalchemy import text
from sqlalchemy.sql import func
from sqlalchemy import Column, TIMESTAMP

created_at = Column(TIMESTAMP, server_default=func.now())

# 1. 새 테이블 생성
Base.metadata.create_all(bind=my_engine)

# 2. 기존 테이블에 컬럼 추가 및 새 테이블 생성
with my_engine.connect() as conn:
    try:
        # users 테이블에 duty_free_type 컬럼 추가
        conn.execute(text("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS duty_free_type VARCHAR(20) DEFAULT 'lotte';
        """))
        print("✅ duty_free_type 컬럼 추가 완료")
        
        # 신라 영수증 테이블 생성
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS shilla_receipts (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) NOT NULL,
                file_path TEXT,
                receipt_number VARCHAR(50),
                passport_number VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        print("✅ shilla_receipts 테이블 생성 완료")
        
        # 기존 사용자들의 duty_free_type을 기본값으로 설정
        conn.execute(text("""
            UPDATE users 
            SET duty_free_type = 'lotte' 
            WHERE duty_free_type IS NULL;
        """))
        print("✅ 기존 사용자 duty_free_type 설정 완료")
        
        conn.commit()
        
    except Exception as e:
        print(f"❌ 마이그레이션 중 오류 발생: {e}")
        conn.rollback()

print("📦 면세점 관련 마이그레이션 완료!")
print("💡 엑셀 데이터 테이블은 업로드 시 동적으로 생성됩니다.")