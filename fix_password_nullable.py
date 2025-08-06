#!/usr/bin/env python3
"""
hashed_password 컬럼의 NOT NULL 제약조건 제거
회원가입 시 비밀번호 없이 등록할 수 있도록 수정
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

def fix_password_constraint():
    """hashed_password 컬럼의 NOT NULL 제약조건 제거"""
    
    engine = create_engine(get_database_url())
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("🔧 hashed_password 컬럼의 NOT NULL 제약조건을 제거합니다...")
        
        # hashed_password 컬럼을 nullable로 변경
        session.execute(text("ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;"))
        session.commit()
        
        print("✅ hashed_password 컬럼이 nullable로 변경되었습니다!")
        
        # 변경사항 확인
        result = session.execute(text("""
            SELECT column_name, is_nullable, data_type
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'hashed_password';
        """))
        
        for row in result:
            print(f"📊 {row.column_name}: {row.data_type} ({'NULL 허용' if row.is_nullable == 'YES' else 'NOT NULL'})")
        
    except Exception as e:
        session.rollback()
        print(f"❌ 작업 중 오류 발생: {str(e)}")
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 YIDOWEB 비밀번호 컬럼 수정 도구")
    print("=" * 60)
    
    try:
        fix_password_constraint()
        print("\n🎉 작업이 완료되었습니다!")
        print("📝 이제 회원가입 시 비밀번호 없이 등록할 수 있습니다.")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 실행 중 오류가 발생했습니다: {str(e)}")
        sys.exit(1)