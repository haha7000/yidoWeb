#!/usr/bin/env python3
"""
비밀번호 재설정 관련 필드 추가 마이그레이션
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

def get_database_url():
    user = os.getenv('DB_USER', 'test_user')
    password = os.getenv('DB_PASSWORD', '0000')
    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '5432')
    database = os.getenv('DB_NAME', 'my_test_db')
    return f'postgresql://{user}:{password}@{host}:{port}/{database}'

def add_password_reset_fields():
    """비밀번호 재설정 관련 필드 추가"""
    
    engine = create_engine(get_database_url())
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("🔧 비밀번호 재설정 관련 필드를 추가합니다...")
        
        # 새로운 필드들 추가
        migration_queries = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(255);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMP;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_temp_password BOOLEAN DEFAULT FALSE;",
            
            # 기존 승인된 사용자들의 is_temp_password 값 설정
            "UPDATE users SET is_temp_password = FALSE WHERE is_temp_password IS NULL;",
            
            # 인덱스 추가 (검색 성능 향상)
            "CREATE INDEX IF NOT EXISTS idx_users_reset_token ON users (reset_token);",
            "CREATE INDEX IF NOT EXISTS idx_users_temp_password ON users (is_temp_password);"
        ]
        
        for i, query in enumerate(migration_queries, 1):
            print(f"📝 [{i}/{len(migration_queries)}] 실행 중: {query.split()[0]} {query.split()[1]} {query.split()[2]}")
            session.execute(text(query))
        
        session.commit()
        print("✅ 비밀번호 재설정 필드 추가가 완료되었습니다!")
        
        # 변경사항 확인
        print("\n📊 추가된 필드들:")
        result = session.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name IN ('reset_token', 'reset_token_expires', 'is_temp_password')
            ORDER BY column_name;
        """))
        
        for row in result:
            print(f"  - {row.column_name}: {row.data_type} ({'NULL 허용' if row.is_nullable == 'YES' else 'NOT NULL'})")
        
    except Exception as e:
        session.rollback()
        print(f"❌ 작업 중 오류 발생: {str(e)}")
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 YIDOWEB 비밀번호 재설정 필드 추가 도구")
    print("=" * 60)
    
    try:
        add_password_reset_fields()
        print("\n🎉 작업이 완료되었습니다!")
        print("📝 이제 비밀번호 재설정 기능을 사용할 수 있습니다.")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 실행 중 오류가 발생했습니다: {str(e)}")
        sys.exit(1)