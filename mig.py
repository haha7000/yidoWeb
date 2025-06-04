# migration_remove_duty_free_type.py
from app.core.database import my_engine
from app.models.models import Base
from sqlalchemy import text

print("📦 면세점 타입 제거 마이그레이션 시작...")

# 1. 새 테이블 구조로 업데이트 (Base.metadata 사용)
try:
    Base.metadata.create_all(bind=my_engine)
    print("✅ 새 테이블 구조 생성 완료")
except Exception as e:
    print(f"⚠️ 테이블 생성 중 오류 (기존 테이블 유지): {e}")

# 2. users 테이블에서 duty_free_type 컬럼 제거
with my_engine.connect() as conn:
    try:
        # 컬럼 존재 여부 확인
        check_column_sql = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'duty_free_type'
        """
        column_exists = conn.execute(text(check_column_sql)).fetchone()
        
        if column_exists:
            # duty_free_type 컬럼 삭제
            conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS duty_free_type"))
            print("✅ users 테이블에서 duty_free_type 컬럼 제거 완료")
        else:
            print("ℹ️ duty_free_type 컬럼이 이미 존재하지 않습니다")
        
        conn.commit()
        
    except Exception as e:
        print(f"❌ 컬럼 제거 중 오류 발생: {e}")
        conn.rollback()

print("📦 면세점 타입 제거 마이그레이션 완료!")
print("💡 이제 사용자는 로그인 후 업로드 화면에서 면세점을 선택할 수 있습니다.")
print("💡 엑셀 데이터 테이블(lotte_excel_data, shilla_excel_data)은 면세점 선택 시 동적으로 생성됩니다.")