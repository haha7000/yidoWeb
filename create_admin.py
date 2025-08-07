#!/usr/bin/env python3
"""
관리자 계정 생성 스크립트
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

def get_database_url():
    user = os.getenv('DB_USER', 'test_user')
    password = os.getenv('DB_PASSWORD', '0000')
    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '5432')
    database = os.getenv('DB_NAME', 'my_test_db')
    return f'postgresql://{user}:{password}@{host}:{port}/{database}'

def create_admin_user():
    """관리자 사용자 생성"""
    engine = create_engine(get_database_url())
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("👤 관리자 계정 생성을 시작합니다...")
        
        # 기존 관리자 계정 확인
        existing_admin = session.query(User).filter(User.username == "yido782").first()
        
        if existing_admin:
            print("⚠️  기존 yido782 계정이 발견되었습니다.")
            if not existing_admin.is_admin:
                print("📝 기존 계정을 관리자로 변경합니다...")
                existing_admin.is_admin = True
                existing_admin.status = "approved"
                existing_admin.is_temp_password = False
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
                is_active=True,
                is_temp_password=False  # 관리자는 임시 비밀번호가 아님
            )
            
            session.add(admin_user)
            session.commit()
            print("✅ 관리자 계정이 생성되었습니다!")
        
        print("\n📋 관리자 계정 정보:")
        print("   아이디: yido782")
        print("   비밀번호: yido2020**")
        print("   관리자 페이지: http://localhost:8000/admin/login (개발 환경)")
        
    except Exception as e:
        session.rollback()
        print(f"❌ 관리자 계정 생성 중 오류 발생: {str(e)}")
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    print("=" * 60)
    print("👤 YIDOWEB 관리자 계정 생성 도구")
    print("=" * 60)
    
    try:
        # 관리자 계정 생성
        create_admin_user()
        
        print("\n" + "=" * 60)
        print("🎉 관리자 계정 생성이 완료되었습니다!")
        print("🌐 관리자 로그인: http://localhost:8000/admin/login (개발 환경)")
        print("🌐 프로덕션 환경에서는 도메인/admin/login 으로 접근하세요")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 실행 중 오류가 발생했습니다: {str(e)}")
        sys.exit(1)