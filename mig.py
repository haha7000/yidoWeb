# migration_add_users.py
from app.core.database import my_engine
from app.models.models import Base
from sqlalchemy import text

# 1. 새 테이블 생성
Base.metadata.create_all(bind=my_engine)

# 2. 기존 테이블에 user_id 컬럼 추가 (수동으로 실행)
with my_engine.connect() as conn:
    # 기본 사용자 생성 (기존 데이터용)
    conn.execute(text("""
        INSERT INTO users (username, email, hashed_password, is_active)
        VALUES ('admin', 'admin@example.com', '$2b$12$example_hash', true)
        ON CONFLICT DO NOTHING;
    """))
    
    # 기존 테이블에 user_id 컬럼 추가
    conn.execute(text("ALTER TABLE receipts ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);"))
    conn.execute(text("ALTER TABLE passports ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);"))
    conn.execute(text("ALTER TABLE receipt_match_log ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);"))
    conn.execute(text("ALTER TABLE unrecognized_images ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);"))
    
    # 기존 데이터에 기본 사용자 ID 할당
    conn.execute(text("UPDATE receipts SET user_id = 1 WHERE user_id IS NULL;"))
    conn.execute(text("UPDATE passports SET user_id = 1 WHERE user_id IS NULL;"))
    conn.execute(text("UPDATE receipt_match_log SET user_id = 1 WHERE user_id IS NULL;"))
    conn.execute(text("UPDATE unrecognized_images SET user_id = 1 WHERE user_id IS NULL;"))
    
    conn.commit()

print("마이그레이션 완료!")