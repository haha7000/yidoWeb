# run_all_migrations.py - 모든 마이그레이션을 순서대로 실행
import sys
import os
from datetime import datetime

print("🚀 OCR 시스템 마이그레이션 시작")
print("=" * 50)
print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("")

def run_migration(migration_name, migration_file):
    """개별 마이그레이션 실행"""
    print(f"📦 {migration_name} 실행 중...")
    try:
        # 마이그레이션 파일 실행
        exec(open(migration_file).read())
        print(f"✅ {migration_name} 완료")
        return True
    except Exception as e:
        print(f"❌ {migration_name} 실패: {e}")
        return False

def main():
    """메인 마이그레이션 실행 함수"""
    
    # 실행할 마이그레이션 목록 (순서 중요!)
    migrations = [
        ("기존 테이블 구조 업데이트", "mig.py"),  # 기존 마이그레이션
        ("아카이브 테이블 추가", "migration_add_archive_tables.py"),
        ("사용자별 데이터 격리 강화", "migration_fix_user_isolation.py")
    ]
    
    success_count = 0
    total_count = len(migrations)
    
    for migration_name, migration_file in migrations:
        print("-" * 30)
        
        # 파일 존재 확인
        if not os.path.exists(migration_file):
            print(f"⚠️ 마이그레이션 파일을 찾을 수 없습니다: {migration_file}")
            print(f"   현재 디렉토리: {os.getcwd()}")
            print(f"   예상 파일 경로: {os.path.abspath(migration_file)}")
            continue
            
        # 마이그레이션 실행
        if run_migration(migration_name, migration_file):
            success_count += 1
        else:
            print(f"❌ {migration_name} 실패로 인해 마이그레이션을 중단합니다.")
            break
            
        print("")
    
    # 결과 요약
    print("ㅋ" * 50)
    print("🏁 마이그레이션 완료 요약")
    print(f"성공: {success_count}/{total_count}")
    
    if success_count == total_count:
        print("✅ 모든 마이그레이션이 성공적으로 완료되었습니다!")
        print("")
        print("💡 새로운 기능들:")
        print("   🔹 사용자별 완전한 데이터 격리")
        print("   🔹 처리 완료 후 자동 초기화")
        print("   🔹 이력 저장 및 검색 기능")
        print("   🔹 과거 처리 결과 조회")
        print("   🔹 통합 검색 (고객명, 여권번호, 영수증번호)")
        print("")
        print("🎯 다음 단계:")
        print("   1. 서버 재시작")
        print("   2. 새로운 엔드포인트 테스트:")
        print("      - POST /complete-session/ (처리 완료)")
        print("      - GET /history/ (이력 조회)")
        print("      - GET /history/search/ (이력 검색)")
        
    else:
        print("❌ 일부 마이그레이션이 실패했습니다.")
        print("💡 실패한 마이그레이션을 확인하고 수정 후 다시 실행하세요.")
    
    print("=" * 50)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 마이그레이션이 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류가 발생했습니다: {e}")
        sys.exit(1)





