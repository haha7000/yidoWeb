#!/usr/bin/env python3
"""
이미 OCR+GPT로 처리된 데이터에 대해서만 매칭 로직을 실행하는 스크립트
네트워크 오류로 중단된 상황에서 이미 처리된 데이터를 매칭하기 위해 사용
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.models import Receipt, ShillaReceipt, Passport, ReceiptMatchLog
from app.services.matching import matchingResult
from app.services.shilla_matching import shilla_matching_result
from sqlalchemy import text
from datetime import datetime

def check_processed_data(user_id: int):
    """처리된 데이터 상태 확인"""
    print("=" * 60)
    print("📊 처리된 데이터 상태 확인")
    print("=" * 60)
    
    with SessionLocal() as db:
        # 롯데 영수증 확인
        lotte_receipts = db.query(Receipt).filter(Receipt.user_id == user_id).count()
        print(f"🏪 롯데 영수증: {lotte_receipts}개")
        
        # 신라 영수증 확인
        shilla_receipts = db.query(ShillaReceipt).filter(ShillaReceipt.user_id == user_id).count()
        print(f"🏨 신라 영수증: {shilla_receipts}개")
        
        # 여권 확인
        passports = db.query(Passport).filter(Passport.user_id == user_id).count()
        print(f"📘 여권: {passports}개")
        
        # 기존 매칭 로그 확인
        existing_logs = db.query(ReceiptMatchLog).filter(ReceiptMatchLog.user_id == user_id).count()
        print(f"📝 기존 매칭 로그: {existing_logs}개")
        
        print()
        
        # 면세점 타입 결정
        if shilla_receipts > 0:
            duty_free_type = "shilla"
            total_receipts = shilla_receipts
        elif lotte_receipts > 0:
            duty_free_type = "lotte"
            total_receipts = lotte_receipts
        else:
            duty_free_type = None
            total_receipts = 0
        
        print(f"🎯 감지된 면세점 타입: {duty_free_type}")
        print(f"📦 총 영수증 수: {total_receipts}개")
        
        return duty_free_type, total_receipts, existing_logs

def run_matching_for_processed_data(user_id: int):
    """처리된 데이터에 대해서만 매칭 실행"""
    start_time = datetime.now()
    print(f"🚀 매칭 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. 데이터 상태 확인
    duty_free_type, total_receipts, existing_logs = check_processed_data(user_id)
    
    if total_receipts == 0:
        print("❌ 처리된 영수증 데이터가 없습니다.")
        return False
    
    if duty_free_type is None:
        print("❌ 면세점 타입을 결정할 수 없습니다.")
        return False
    
    # 2. 기존 매칭 로그가 있는 경우 확인
    if existing_logs > 0:
        response = input(f"⚠️ 기존 매칭 로그 {existing_logs}개가 있습니다. 다시 매칭하시겠습니까? (y/N): ")
        if response.lower() != 'y':
            print("📝 매칭을 취소했습니다.")
            return False
        
        # 기존 매칭 로그 삭제
        print(f"🗑️ 기존 매칭 로그 {existing_logs}개를 삭제합니다...")
        with SessionLocal() as db:
            deleted = db.query(ReceiptMatchLog).filter(ReceiptMatchLog.user_id == user_id).delete()
            db.commit()
            print(f"✅ {deleted}개의 기존 매칭 로그를 삭제했습니다.")
    
    # 3. 매칭 실행
    print("=" * 60)
    print("🔄 매칭 로직 실행")
    print("=" * 60)
    
    try:
        if duty_free_type == "lotte":
            print("🏪 롯데 면세점 매칭을 시작합니다...")
            matchingResult(user_id)
            print("✅ 롯데 매칭 완료!")
        
        elif duty_free_type == "shilla":
            print("🏨 신라 면세점 매칭을 시작합니다...")
            shilla_matching_result(user_id)
            print("✅ 신라 매칭 완료!")
        
        # 4. 매칭 결과 확인
        print("\n" + "=" * 60)
        print("📊 매칭 결과 확인")
        print("=" * 60)
        
        with SessionLocal() as db:
            # 매칭된 결과 확인
            matched_count = db.query(ReceiptMatchLog).filter(
                ReceiptMatchLog.user_id == user_id,
                ReceiptMatchLog.is_matched == True
            ).count()
            
            unmatched_count = db.query(ReceiptMatchLog).filter(
                ReceiptMatchLog.user_id == user_id,
                ReceiptMatchLog.is_matched == False
            ).count()
            
            total_logs = matched_count + unmatched_count
            
            print(f"📝 생성된 매칭 로그: {total_logs}개")
            print(f"✅ 매칭 성공: {matched_count}개")
            print(f"❌ 매칭 실패: {unmatched_count}개")
            
            if total_logs > 0:
                success_rate = (matched_count / total_logs) * 100
                print(f"📈 매칭 성공률: {success_rate:.1f}%")
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        print(f"\n🏁 매칭 완료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️ 총 처리 시간: {processing_time:.1f}초")
        
        return True
        
    except Exception as e:
        print(f"❌ 매칭 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 함수"""
    print("🔄 OCR+GPT 처리 완료 데이터 매칭 스크립트")
    print("=" * 60)
    
    # 사용자 ID 입력
    try:
        user_id = int(input("👤 사용자 ID를 입력하세요: "))
    except ValueError:
        print("❌ 올바른 사용자 ID를 입력해주세요.")
        return False
    
    # 사용자 확인
    with SessionLocal() as db:
        user_exists = db.execute(text("SELECT COUNT(*) FROM users WHERE id = :user_id"), 
                                {"user_id": user_id}).scalar()
        if not user_exists:
            print(f"❌ 사용자 ID {user_id}가 존재하지 않습니다.")
            return False
    
    print(f"✅ 사용자 ID {user_id} 확인 완료\n")
    
    # 매칭 실행
    success = run_matching_for_processed_data(user_id)
    
    if success:
        print("\n🎉 모든 매칭이 성공적으로 완료되었습니다!")
        print("💡 이제 웹 인터페이스에서 결과를 확인하실 수 있습니다.")
    else:
        print("\n❌ 매칭 처리 중 문제가 발생했습니다.")
    
    return success

if __name__ == "__main__":
    main() 