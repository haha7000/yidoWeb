#!/usr/bin/env python3
"""
신라 면세점 매칭 실행 스크립트
실제 운영 데이터에 대해 수정된 신라 매칭 로직을 실행합니다.
"""

import sys
import os
from datetime import datetime

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.services.shilla_matching import shilla_matching_result, fetch_shilla_results_with_details
from app.models.models import User, ReceiptMatchLog
from sqlalchemy import text


def get_user_by_id(user_id):
    """사용자 ID로 사용자 정보 조회"""
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            print(f"❌ 사용자 ID {user_id}를 찾을 수 없습니다.")
            return None
        print(f"✅ 사용자 확인: {user.username} (ID: {user.id})")
        return user


def check_data_status(user_id):
    """현재 데이터 상태 확인"""
    with SessionLocal() as db:
        print("\n📊 현재 데이터 상태:")
        
        # 여권 수
        passport_count = db.execute(text("SELECT COUNT(*) FROM passports WHERE user_id = :user_id"), {"user_id": user_id}).scalar()
        matched_passport_count = db.execute(text("SELECT COUNT(*) FROM passports WHERE user_id = :user_id AND is_matched = TRUE"), {"user_id": user_id}).scalar()
        
        # 신라 영수증 수  
        receipt_count = db.execute(text("SELECT COUNT(*) FROM shilla_receipts WHERE user_id = :user_id"), {"user_id": user_id}).scalar()
        
        # 신라 엑셀 데이터 수
        excel_count = db.execute(text("SELECT COUNT(*) FROM shilla_excel_data")).scalar()
        
        # 기존 매칭 로그 수
        existing_logs = db.execute(text("SELECT COUNT(*) FROM receipt_match_log WHERE user_id = :user_id"), {"user_id": user_id}).scalar()
        
        print(f"  - 전체 여권: {passport_count}개 (매칭됨: {matched_passport_count}개)")
        print(f"  - 신라 영수증: {receipt_count}개")
        print(f"  - 신라 엑셀 데이터: {excel_count}개")
        print(f"  - 기존 매칭 로그: {existing_logs}개")
        
        if passport_count == 0:
            print("⚠️ 여권 데이터가 없습니다. 먼저 여권 이미지를 업로드해주세요.")
            return False
            
        if receipt_count == 0:
            print("⚠️ 신라 영수증 데이터가 없습니다. 먼저 영수증 이미지를 업로드해주세요.")
            return False
            
        if excel_count == 0:
            print("⚠️ 신라 엑셀 데이터가 없습니다. 먼저 엑셀 파일을 업로드해주세요.")
            return False
            
        return True


def run_shilla_matching(user_id):
    """신라 매칭 로직 실행"""
    print(f"\n🔄 신라 매칭 로직 실행 중... (사용자 ID: {user_id})")
    print("=" * 60)
    
    start_time = datetime.now()
    
    try:
        # 매칭 실행
        shilla_matching_result(user_id)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        print(f"\n✅ 신라 매칭 완료! (소요시간: {processing_time:.1f}초)")
        
        return True
        
    except Exception as e:
        print(f"❌ 매칭 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def show_results(user_id):
    """매칭 결과 표시"""
    with SessionLocal() as db:
        print("\n📊 매칭 후 결과:")
        print("=" * 60)
        
        # 매칭 로그 통계
        total_logs = db.execute(text("SELECT COUNT(*) FROM receipt_match_log WHERE user_id = :user_id"), {"user_id": user_id}).scalar()
        matched_logs = db.execute(text("SELECT COUNT(*) FROM receipt_match_log WHERE user_id = :user_id AND is_matched = TRUE"), {"user_id": user_id}).scalar()
        unmatched_logs = total_logs - matched_logs
        
        # 여권 통계
        total_passports = db.execute(text("SELECT COUNT(*) FROM passports WHERE user_id = :user_id"), {"user_id": user_id}).scalar()
        matched_passports = db.execute(text("SELECT COUNT(*) FROM passports WHERE user_id = :user_id AND is_matched = TRUE"), {"user_id": user_id}).scalar()
        
        print(f"📝 매칭 로그:")
        print(f"  - 총 로그: {total_logs}개")
        print(f"  - 매칭 성공: {matched_logs}개")
        print(f"  - 매칭 실패: {unmatched_logs}개")
        print(f"  - 성공률: {(matched_logs/total_logs*100):.1f}%" if total_logs > 0 else "  - 성공률: 0%")
        
        print(f"\n👥 여권 상태:")
        print(f"  - 전체 여권: {total_passports}개")
        print(f"  - 매칭된 여권: {matched_passports}개")
        print(f"  - 매칭률: {(matched_passports/total_passports*100):.1f}%" if total_passports > 0 else "  - 매칭률: 0%")
        
        # 결과 조회 테스트
        try:
            print(f"\n🔍 고객별 매칭 결과:")
            matched_list, unmatched_list = fetch_shilla_results_with_details(user_id)
            
            print(f"  - 매칭된 고객: {len(matched_list)}명")
            print(f"  - 매칭안된 영수증: {len(unmatched_list)}개")
            
            # 상위 5명 고객 표시
            print(f"\n📋 매칭된 고객 상세 (상위 5명):")
            for i, customer in enumerate(matched_list[:5]):
                print(f"  {i+1}. {customer['name']} ({customer['passport_match_status']})")
                print(f"     - 여권번호: {customer.get('passport_number', 'N/A')}")
                print(f"     - 영수증 수: {len(customer['receipt_numbers'])}개")
                
        except Exception as e:
            print(f"⚠️ 결과 조회 중 오류: {e}")


def main():
    """메인 함수"""
    print("🚀 신라 면세점 매칭 실행 스크립트")
    print("=" * 60)
    
    # 사용자 ID 입력
    if len(sys.argv) > 1:
        try:
            user_id = int(sys.argv[1])
        except ValueError:
            print("❌ 올바른 사용자 ID를 입력해주세요.")
            print("사용법: python run_shilla_matching.py <user_id>")
            sys.exit(1)
    else:
        try:
            user_id = int(input("사용자 ID를 입력하세요: "))
        except ValueError:
            print("❌ 올바른 숫자를 입력해주세요.")
            sys.exit(1)
    
    # 1. 사용자 확인
    user = get_user_by_id(user_id)
    if not user:
        sys.exit(1)
    
    # 2. 데이터 상태 확인
    if not check_data_status(user_id):
        print("\n❌ 필요한 데이터가 부족합니다. 먼저 데이터를 업로드해주세요.")
        sys.exit(1)
    
    # 3. 실행 확인
    print(f"\n⚠️ 사용자 '{user.username}'의 신라 매칭을 실행하시겠습니까?")
    print("   기존 매칭 로그가 삭제되고 새로 생성됩니다.")
    
    if len(sys.argv) <= 1:  # 대화형 모드
        confirm = input("계속하시겠습니까? (y/N): ").lower()
        if confirm not in ['y', 'yes']:
            print("❌ 실행이 취소되었습니다.")
            sys.exit(0)
    
    # 4. 매칭 실행
    if not run_shilla_matching(user_id):
        print("\n❌ 매칭 실행에 실패했습니다.")
        sys.exit(1)
    
    # 5. 결과 표시
    show_results(user_id)
    
    print("\n" + "=" * 60)
    print("🎉 신라 매칭 완료! 이제 웹에서 결과를 확인하세요.")
    print("   💡 다음 단계: 할인율·수수료 계산 버튼을 클릭하세요.")


if __name__ == "__main__":
    main() 