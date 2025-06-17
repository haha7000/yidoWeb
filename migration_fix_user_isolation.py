# debug_shilla_matching.py - 신라 매칭 상태 디버깅
from app.core.database import my_engine
from sqlalchemy import text

def debug_shilla_matching_status(user_id, receipt_number=None):
    """신라 매칭 상태를 자세히 분석하는 함수"""
    print(f"🔍 신라 매칭 상태 디버깅 - 사용자 {user_id}")
    
    with my_engine.connect() as conn:
        
        # 1. 특정 영수증이 있다면 해당 영수증만, 없다면 모든 영수증 조회
        if receipt_number:
            where_clause = f"AND sr.receipt_number = '{receipt_number}'"
            print(f"🎯 특정 영수증 조회: {receipt_number}")
        else:
            where_clause = ""
            print("📋 모든 영수증 조회")
        
        # 신라 영수증과 관련된 모든 정보 조회
        debug_sql = f"""
        SELECT 
            sr.receipt_number,
            sr.passport_number as receipt_passport,
            se.passport_number as excel_passport,
            se.name as excel_name,
            p.name as passport_name,
            p.passport_number as passport_passport,
            p.is_matched as passport_is_matched,
            CASE 
                WHEN p.passport_number IS NOT NULL AND p.is_matched = TRUE THEN 'passport_matched'
                WHEN p.passport_number IS NOT NULL AND p.is_matched = FALSE THEN 'passport_needs_update'  
                WHEN p.passport_number IS NULL AND (sr.passport_number IS NOT NULL OR se.passport_number IS NOT NULL) THEN 'passport_missing'
                WHEN p.passport_number IS NULL AND sr.passport_number IS NULL AND se.passport_number IS NULL THEN 'passport_not_provided'
                ELSE 'passport_unknown'
            END as passport_status
        FROM shilla_receipts sr
        LEFT JOIN shilla_excel_data se ON se."receiptNumber"::text = sr.receipt_number
        LEFT JOIN passports p ON (
            sr.passport_number = p.passport_number 
            OR se.passport_number = p.passport_number
        ) AND p.user_id = :user_id
        WHERE sr.user_id = :user_id {where_clause}
        ORDER BY sr.receipt_number
        """
        
        results = conn.execute(text(debug_sql), {"user_id": user_id}).fetchall()
        
        print(f"\n📊 조회 결과: {len(results)}개")
        print("=" * 120)
        
        for i, row in enumerate(results, 1):
            (receipt_num, receipt_passport, excel_passport, excel_name, 
             passport_name, passport_passport, passport_is_matched, passport_status) = row
            
            print(f"\n🎫 {i}. 영수증: {receipt_num}")
            print(f"   📄 영수증 여권번호: {receipt_passport or 'None'}")
            print(f"   📊 엑셀 여권번호:   {excel_passport or 'None'}")
            print(f"   📊 엑셀 이름:       {excel_name or 'None'}")
            print(f"   🛂 여권 이름:       {passport_name or 'None'}")
            print(f"   🛂 여권 여권번호:   {passport_passport or 'None'}")
            print(f"   🛂 여권 매칭상태:   {passport_is_matched}")
            print(f"   🎯 최종 상태:       {passport_status}")
            
            # 매칭 분석
            print(f"   📝 매칭 분석:")
            if receipt_passport and passport_passport:
                if receipt_passport == passport_passport:
                    print(f"      ✅ 영수증-여권 매칭: {receipt_passport} == {passport_passport}")
                else:
                    print(f"      ❌ 영수증-여권 불일치: {receipt_passport} != {passport_passport}")
            
            if excel_passport and passport_passport:
                if excel_passport == passport_passport:
                    print(f"      ✅ 엑셀-여권 매칭: {excel_passport} == {passport_passport}")
                else:
                    print(f"      ❌ 엑셀-여권 불일치: {excel_passport} != {passport_passport}")
            
            # 문제점 분석
            if passport_status == 'passport_needs_update':
                print(f"   ⚠️  문제 분석:")
                print(f"      - 여권번호는 매칭되지만 is_matched=FALSE인 상태")
                print(f"      - 이는 여권 테이블의 is_matched 필드가 업데이트되지 않았음을 의미")
            
            print("-" * 120)
        
        # 여권 테이블 상태 확인
        print(f"\n🛂 여권 테이블 상태 확인:")
        passport_sql = """
        SELECT 
            name, 
            passport_number, 
            is_matched,
            birthday
        FROM passports 
        WHERE user_id = :user_id
        ORDER BY name
        """
        passport_results = conn.execute(text(passport_sql), {"user_id": user_id}).fetchall()
        
        for name, passport_num, is_matched, birthday in passport_results:
            print(f"   👤 {name}: {passport_num} (매칭: {is_matched}) - 생일: {birthday}")

# 사용 예시
if __name__ == "__main__":
    # 특정 사용자의 매칭 상태 확인
    debug_shilla_matching_status(user_id=2)
    
    # 또는 특정 영수증만 확인
    # debug_shilla_matching_status(user_id=2, receipt_number="0124502900965")