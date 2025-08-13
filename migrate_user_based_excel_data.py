#!/usr/bin/env python3
"""
사용자별 엑셀 데이터 테이블 마이그레이션 스크립트
- 기존 lotte_excel_data, shilla_excel_data 삭제
- 새로운 구조로 테이블 재생성 (user_id 포함)
- 새로운 테이블들 추가 (duty_free_accounts, automation_logs, shilla_excel_data)
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

from app.models.models import Base, User, DutyFreeAccount, AutomationLog, LotteExcelData, ShillaExcelData

def get_database_url():
    """데이터베이스 연결 URL 생성"""
    user = os.getenv('DB_USER', 'test_user')
    password = os.getenv('DB_PASSWORD', '0000')
    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '5432')
    database = os.getenv('DB_NAME', 'my_test_db')
    return f'postgresql://{user}:{password}@{host}:{port}/{database}'

def run_migration():
    """마이그레이션 실행"""
    
    print("🔄 사용자별 엑셀 데이터 마이그레이션을 시작합니다...")
    
    # 데이터베이스 연결
    engine = create_engine(get_database_url())
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 1. 기존 엑셀 데이터 테이블들 삭제 (CASCADE로 관련 데이터도 함께 삭제)
        print("\n📦 1단계: 기존 엑셀 데이터 테이블 삭제...")
        
        tables_to_drop = [
            "automation_logs",     # 새 테이블이지만 혹시 있다면 삭제
            "duty_free_accounts",  # 새 테이블이지만 혹시 있다면 삭제
            "shilla_excel_data",   # 새로 만들 테이블
            "lotte_excel_data"     # 기존 테이블 (user_id 없음)
        ]
        
        for table in tables_to_drop:
            try:
                result = session.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE;"))
                session.commit()
                print(f"✅ {table} 테이블 삭제 완료")
            except Exception as e:
                print(f"⚠️ {table} 테이블 삭제 중 오류 (무시): {e}")
                session.rollback()
        
        # 2. 새로운 테이블들 생성
        print("\n🔧 2단계: 새로운 테이블 구조 생성...")
        
        # 특정 테이블들만 생성 (기존 테이블은 유지)
        tables_to_create = [
            DutyFreeAccount.__table__,
            AutomationLog.__table__, 
            LotteExcelData.__table__,
            ShillaExcelData.__table__
        ]
        
        for table in tables_to_create:
            try:
                table.create(engine, checkfirst=True)
                print(f"✅ {table.name} 테이블 생성 완료")
            except Exception as e:
                print(f"❌ {table.name} 테이블 생성 실패: {e}")
                raise e
        
        # 3. 생성된 테이블 확인
        print("\n📋 3단계: 생성된 테이블 확인...")
        result = session.execute(text("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename IN ('duty_free_accounts', 'automation_logs', 'lotte_excel_data', 'shilla_excel_data')
            ORDER BY tablename;
        """))
        
        created_tables = [row[0] for row in result]
        print(f"📋 새로 생성된 테이블: {', '.join(created_tables)}")
        
        # 4. 테이블 구조 확인
        print("\n🔍 4단계: 테이블 구조 확인...")
        for table_name in created_tables:
            result = session.execute(text(f"""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = '{table_name}' 
                ORDER BY ordinal_position;
            """))
            
            columns = [(row[0], row[1], row[2]) for row in result]
            print(f"\n📄 {table_name} 테이블 구조:")
            for col_name, data_type, nullable in columns:
                print(f"  - {col_name}: {data_type} ({'NULL' if nullable == 'YES' else 'NOT NULL'})")
        
        session.commit()
        print("\n✅ 마이그레이션이 성공적으로 완료되었습니다!")
        
        print("\n💡 다음 단계:")
        print("1. 사용자가 면세점 계정을 등록할 수 있는 웹 인터페이스 개발")
        print("2. 자동화 스크립트를 사용자별로 실행하도록 수정")
        print("3. 매칭 로직에 user_id 필터링 추가")
        
    except Exception as e:
        print(f"❌ 마이그레이션 중 오류 발생: {e}")
        session.rollback()
        raise e
        
    finally:
        session.close()

if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"\n💥 마이그레이션 실패: {e}")
        sys.exit(1)