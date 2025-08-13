#!/usr/bin/env python3
"""
수수료 설정에 user_id 필드 추가 마이그레이션 스크립트

기존 fee_settings 테이블에 user_id 컬럼을 추가하고, 기존 데이터는 creator_id 값을 user_id로 복사합니다.
새로운 로직에서는 수수료 설정이 사용자별로 격리됩니다.

실행 방법:
python migrate_fee_settings_user_id.py [--dry-run]
"""

import os
import sys
import argparse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_database_url():
    """환경변수에서 데이터베이스 URL을 가져옵니다"""
    user = os.getenv('DB_USER', 'test_user')
    password = os.getenv('DB_PASSWORD', '0000')
    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '5432')
    database = os.getenv('DB_NAME', 'my_test_db')
    
    return f'postgresql://{user}:{password}@{host}:{port}/{database}'

def check_migration_needed(session):
    """마이그레이션이 필요한지 확인"""
    try:
        # user_id 컬럼이 이미 존재하는지 확인
        result = session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'fee_settings' 
            AND column_name = 'user_id'
        """)).first()
        
        if result:
            print("✅ user_id 컬럼이 이미 존재합니다.")
            return False
        
        # 기존 데이터 확인
        count_result = session.execute(text("SELECT COUNT(*) FROM fee_settings")).scalar()
        print(f"📊 기존 fee_settings 데이터: {count_result}건")
        
        return True
        
    except Exception as e:
        print(f"❌ 마이그레이션 필요성 확인 중 오류: {e}")
        return False

def perform_migration(session, dry_run=False):
    """실제 마이그레이션 실행"""
    try:
        print("🚀 마이그레이션 시작...")
        
        if dry_run:
            print("🔍 DRY RUN 모드: 실제 변경은 하지 않습니다.")
        
        # 1. user_id 컬럼 추가 (nullable로 먼저 추가)
        print("1️⃣ user_id 컬럼 추가 중...")
        if not dry_run:
            session.execute(text("""
                ALTER TABLE fee_settings 
                ADD COLUMN user_id INTEGER
            """))
            session.commit()
        print("   ✅ user_id 컬럼 추가 완료")
        
        # 2. 기존 데이터의 creator_id를 user_id로 복사
        print("2️⃣ 기존 데이터 업데이트 중...")
        update_query = text("""
            UPDATE fee_settings 
            SET user_id = creator_id 
            WHERE user_id IS NULL AND creator_id IS NOT NULL
        """)
        
        if not dry_run:
            result = session.execute(update_query)
            updated_count = result.rowcount
            session.commit()
            print(f"   ✅ {updated_count}건의 데이터 업데이트 완료")
        else:
            # Dry run에서는 실제 업데이트할 데이터 수만 확인
            count_result = session.execute(text("""
                SELECT COUNT(*) FROM fee_settings 
                WHERE creator_id IS NOT NULL
            """)).scalar()
            print(f"   🔍 업데이트 예정 데이터: {count_result}건")
        
        # 3. user_id를 NOT NULL로 변경 (데이터가 없으면 기본값 설정)
        print("3️⃣ user_id 컬럼을 필수로 변경 중...")
        
        # 먼저 NULL 값이 있는지 확인
        null_count = session.execute(text("""
            SELECT COUNT(*) FROM fee_settings WHERE user_id IS NULL
        """)).scalar()
        
        if null_count > 0:
            print(f"   ⚠️  user_id가 NULL인 데이터 {null_count}건 발견")
            
            # 관리자 사용자 찾기 (is_admin = true)
            admin_user = session.execute(text("""
                SELECT id FROM users WHERE is_admin = true LIMIT 1
            """)).first()
            
            if admin_user:
                admin_id = admin_user[0]
                print(f"   🔧 관리자 사용자(ID: {admin_id})로 NULL 데이터 할당")
                
                if not dry_run:
                    session.execute(text("""
                        UPDATE fee_settings 
                        SET user_id = :admin_id 
                        WHERE user_id IS NULL
                    """), {"admin_id": admin_id})
                    session.commit()
            else:
                # 관리자가 없으면 첫 번째 사용자 사용
                first_user = session.execute(text("""
                    SELECT id FROM users LIMIT 1
                """)).first()
                
                if first_user:
                    first_id = first_user[0]
                    print(f"   🔧 첫 번째 사용자(ID: {first_id})로 NULL 데이터 할당")
                    
                    if not dry_run:
                        session.execute(text("""
                            UPDATE fee_settings 
                            SET user_id = :first_id 
                            WHERE user_id IS NULL
                        """), {"first_id": first_id})
                        session.commit()
                else:
                    print("   ❌ 사용자 데이터가 없어 NULL 값을 처리할 수 없습니다.")
                    return False
        
        # NOT NULL 제약조건 추가
        if not dry_run:
            session.execute(text("""
                ALTER TABLE fee_settings 
                ALTER COLUMN user_id SET NOT NULL
            """))
            session.commit()
        print("   ✅ user_id 컬럼을 필수로 변경 완료")
        
        # 4. 외래키 제약조건 추가
        print("4️⃣ 외래키 제약조건 추가 중...")
        if not dry_run:
            session.execute(text("""
                ALTER TABLE fee_settings 
                ADD CONSTRAINT fk_fee_settings_user_id 
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            """))
            session.commit()
        print("   ✅ 외래키 제약조건 추가 완료")
        
        # 5. 결과 확인
        if not dry_run:
            final_count = session.execute(text("""
                SELECT COUNT(*) FROM fee_settings WHERE user_id IS NOT NULL
            """)).scalar()
            print(f"📊 마이그레이션 완료: {final_count}건의 데이터가 user_id를 가지고 있습니다.")
        
        return True
        
    except Exception as e:
        session.rollback()
        print(f"❌ 마이그레이션 중 오류 발생: {e}")
        return False

def create_rollback_script():
    """롤백 스크립트 생성"""
    rollback_script = """
-- 수수료 설정 user_id 마이그레이션 롤백 스크립트
-- 주의: 이 스크립트 실행 시 사용자별 격리 설정이 해제됩니다!

BEGIN;

-- 1. 외래키 제약조건 제거
ALTER TABLE fee_settings DROP CONSTRAINT IF EXISTS fk_fee_settings_user_id;

-- 2. user_id 컬럼 제거
ALTER TABLE fee_settings DROP COLUMN IF EXISTS user_id;

COMMIT;

-- 롤백 완료 메시지
SELECT '롤백 완료: fee_settings에서 user_id 컬럼이 제거되었습니다.' as message;
"""
    
    with open('rollback_fee_settings_user_id.sql', 'w', encoding='utf-8') as f:
        f.write(rollback_script)
    
    print("📝 롤백 스크립트 생성: rollback_fee_settings_user_id.sql")

def main():
    parser = argparse.ArgumentParser(description='수수료 설정 user_id 필드 마이그레이션')
    parser.add_argument('--dry-run', action='store_true', 
                       help='실제 변경하지 않고 시뮬레이션만 실행')
    parser.add_argument('--create-rollback', action='store_true',
                       help='롤백 스크립트만 생성하고 종료')
    
    args = parser.parse_args()
    
    if args.create_rollback:
        create_rollback_script()
        return
    
    print("=" * 60)
    print("🔧 수수료 설정 사용자별 격리 마이그레이션")
    print("=" * 60)
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"모드: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print("")
    
    # 데이터베이스 연결
    try:
        db_url = get_database_url()
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        print(f"📡 데이터베이스 연결: {db_url.split('@')[1]}")  # 비밀번호 숨김
        
        # 마이그레이션 필요성 확인
        if not check_migration_needed(session):
            print("✅ 마이그레이션이 이미 완료되었습니다.")
            return
        
        # 사용자 확인 프롬프트
        if not args.dry_run:
            print("\n⚠️  이 마이그레이션은 다음과 같은 변경을 수행합니다:")
            print("   1. fee_settings 테이블에 user_id 컬럼 추가")
            print("   2. 기존 creator_id 값을 user_id로 복사")
            print("   3. user_id를 필수 필드로 설정")
            print("   4. 외래키 제약조건 추가")
            print("")
            
            confirm = input("계속 진행하시겠습니까? (yes/no): ")
            if confirm.lower() not in ['yes', 'y']:
                print("🚫 마이그레이션이 취소되었습니다.")
                return
        
        # 마이그레이션 실행
        success = perform_migration(session, args.dry_run)
        
        if success:
            print("\n" + "=" * 60)
            print("🎉 마이그레이션이 성공적으로 완료되었습니다!")
            print("=" * 60)
            
            if not args.dry_run:
                create_rollback_script()
                
                print("\n📋 다음 단계:")
                print("   1. 애플리케이션을 재시작하여 새로운 모델 구조를 적용하세요.")
                print("   2. 각 사용자별로 수수료 설정이 격리되어 동작하는지 확인하세요.")
                print("   3. 문제가 발생하면 rollback_fee_settings_user_id.sql을 실행하세요.")
        else:
            print("\n❌ 마이그레이션이 실패했습니다.")
            
    except Exception as e:
        print(f"❌ 데이터베이스 연결 오류: {e}")
        return
    
    finally:
        if 'session' in locals():
            session.close()

if __name__ == "__main__":
    main()