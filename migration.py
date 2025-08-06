#!/usr/bin/env python3
"""
데이터베이스 마이그레이션 스크립트
새로운 User 모델 컬럼들을 기존 테이블에 추가
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 환경변수 로드
load_dotenv()

from app.core.config import settings
from app.models.models import User
from passlib.context import CryptContext

# 데이터베이스 연결 정보 직접 구성
def get_database_url():
    user = os.getenv('DB_USER', 'test_user')
    password = os.getenv('DB_PASSWORD', '0000')
    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '5432')
    database = os.getenv('DB_NAME', 'my_test_db')
    return f'postgresql://{user}:{password}@{host}:{port}/{database}'

def run_migration():
    """데이터베이스 마이그레이션 실행"""
    
    # 데이터베이스 연결
    engine = create_engine(get_database_url())
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("🔄 데이터베이스 마이그레이션을 시작합니다...")
        
        # 1. 새로운 컬럼들 추가
        migration_queries = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_name VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS position VARCHAR(50);", 
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'pending';",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS approved_by INTEGER;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP;",
            
            # 2. 기존 사용자들의 기본값 설정
            "UPDATE users SET status = 'approved' WHERE status IS NULL;",
            "UPDATE users SET is_admin = FALSE WHERE is_admin IS NULL;",
            
            # 3. 외래키 제약조건 추가 (approved_by -> users.id)
            """ALTER TABLE users ADD CONSTRAINT fk_users_approved_by 
               FOREIGN KEY (approved_by) REFERENCES users(id) 
               ON DELETE SET NULL;""",
            
            # 4. 회사명 중복 방지를 위한 인덱스 추가
            "CREATE INDEX IF NOT EXISTS idx_users_company_name_lower ON users (LOWER(TRIM(company_name)));",
            
            # 5. 상태별 조회 성능을 위한 인덱스 추가
            "CREATE INDEX IF NOT EXISTS idx_users_status ON users (status);",
            "CREATE INDEX IF NOT EXISTS idx_users_is_admin ON users (is_admin);"
        ]
        
        for i, query in enumerate(migration_queries, 1):
            print(f"📝 [{i}/{len(migration_queries)}] 실행 중: {query.split()[0]} {query.split()[1]} {query.split()[2]}")
            session.execute(text(query))
        
        session.commit()
        print("✅ 데이터베이스 마이그레이션이 완료되었습니다!")
        
        # 테이블 구조 확인
        print("\n📊 현재 users 테이블 구조:")
        result = session.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            ORDER BY ordinal_position;
        """))
        
        for row in result:
            print(f"  - {row.column_name}: {row.data_type} ({'NULL' if row.is_nullable == 'YES' else 'NOT NULL'})")
        
    except Exception as e:
        session.rollback()
        print(f"❌ 마이그레이션 중 오류 발생: {str(e)}")
        raise e
    finally:
        session.close()

def create_admin_user():
    """관리자 사용자 생성"""
    engine = create_engine(get_database_url())
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("\n👤 관리자 계정 생성을 시작합니다...")
        
        # 기존 관리자 계정 확인
        existing_admin = session.query(User).filter(User.username == "yido782").first()
        
        if existing_admin:
            print("⚠️  기존 yido782 계정이 발견되었습니다.")
            if not existing_admin.is_admin:
                print("📝 기존 계정을 관리자로 변경합니다...")
                existing_admin.is_admin = True
                existing_admin.status = "approved"
                if not existing_admin.hashed_password:
                    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
                    existing_admin.hashed_password = pwd_context.hash("yido2020**")
                session.commit()
                print("✅ 기존 계정이 관리자로 변경되었습니다!")
            else:
                print("✅ 이미 관리자 계정이 설정되어 있습니다.")
        else:
            print("📝 새로운 관리자 계정을 생성합니다...")
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            
            admin_user = User(
                username="yido782",
                email="admin@yidoweb.com",
                hashed_password=pwd_context.hash("yido2020**"),
                company_name="이도회계법인",
                position="시스템관리자",
                is_admin=True,
                status="approved",
                is_active=True
            )
            
            session.add(admin_user)
            session.commit()
            print("✅ 관리자 계정이 생성되었습니다!")
            print("   아이디: yido782")
            print("   비밀번호: yido2020**")
        
    except Exception as e:
        session.rollback()
        print(f"❌ 관리자 계정 생성 중 오류 발생: {str(e)}")
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 YIDOWEB 데이터베이스 마이그레이션 도구")
    print("=" * 60)
    
    try:
        # 1. 마이그레이션 실행
        run_migration()
        
        # 2. 관리자 계정 생성
        create_admin_user()
        
        print("\n" + "=" * 60)
        print("🎉 모든 작업이 완료되었습니다!")
        print("🌐 관리자 로그인: http://localhost:8000/admin/login")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 실행 중 오류가 발생했습니다: {str(e)}")
        sys.exit(1)