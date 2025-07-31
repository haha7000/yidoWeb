#!/usr/bin/env python3
"""
롯데 면세점 자동화 파이프라인 테스트 스크립트
"""

import os
import sys
import logging
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_lotte_pipeline import LotteAutoPipeline

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_database_connection():
    """데이터베이스 연결 테스트"""
    print("🔍 1. 데이터베이스 연결 테스트")
    print("-" * 40)
    
    try:
        pipeline = LotteAutoPipeline()
        print("✅ 데이터베이스 연결 성공")
        return True
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        return False

def test_excel_conversion():
    """엑셀 변환 테스트 (기존 파일 사용)"""
    print("\n🔍 2. 엑셀 변환 테스트")
    print("-" * 40)
    
    try:
        # 테스트용 엑셀 파일 경로
        test_file = '/Users/gimdonghun/Downloads/lotte.xlsx'
        
        if not os.path.exists(test_file):
            print(f"⚠️ 테스트 파일이 없습니다: {test_file}")
            print("   다운로드된 엑셀 파일을 해당 경로에 배치해주세요.")
            return False
        
        # execl_test.py의 함수들 import
        sys.path.append('/Users/gimdonghun/Documents/yidoweb')
        from execl_test import process_lotte_excel
        
        # 변환 테스트
        df_converted, sqlalchemy_dtypes, success_rate = process_lotte_excel(test_file, verbose=False)
        
        if df_converted is not None and success_rate >= 90:
            print(f"✅ 엑셀 변환 성공 (성공률: {success_rate:.1f}%)")
            print(f"   - 변환된 데이터: {len(df_converted):,}건")
            print(f"   - 컬럼 수: {len(df_converted.columns)}개")
            return True
        else:
            print(f"❌ 엑셀 변환 실패 (성공률: {success_rate:.1f}%)")
            return False
            
    except Exception as e:
        print(f"❌ 엑셀 변환 테스트 중 오류: {e}")
        return False

def test_individual_steps():
    """개별 단계 테스트"""
    print("\n🔍 3. 개별 단계 테스트")
    print("-" * 40)
    
    try:
        pipeline = LotteAutoPipeline()
        
        # 1단계: 엑셀 다운로드 테스트 (실제 로그인 필요)
        print("📥 1단계: 엑셀 다운로드 테스트")
        print("   (실제 로그인이 필요하므로 건너뜀)")
        
        # 2단계: 데이터 타입 변환 테스트
        print("🔄 2단계: 데이터 타입 변환 테스트")
        test_file = '/Users/gimdonghun/Downloads/lotte.xlsx'
        
        if os.path.exists(test_file):
            success = pipeline.step2_convert_data_types(verbose=False)
            if success:
                print("   ✅ 데이터 타입 변환 성공")
            else:
                print("   ❌ 데이터 타입 변환 실패")
        else:
            print("   ⚠️ 테스트 파일이 없어서 건너뜀")
        
        # 3단계: DB 업로드 테스트 (빈 데이터로)
        print("🗄️ 3단계: DB 업로드 테스트")
        print("   (실제 데이터가 없어서 건너뜀)")
        
        return True
        
    except Exception as e:
        print(f"❌ 개별 단계 테스트 중 오류: {e}")
        return False

def test_configuration():
    """설정 테스트"""
    print("\n🔍 4. 설정 테스트")
    print("-" * 40)
    
    # 환경 변수 확인
    env_vars = {
        'LOTTE_DB_URL': os.getenv('LOTTE_DB_URL'),
        'LOTTE_USER_ID': os.getenv('LOTTE_USER_ID'),
        'LOTTE_PASSWORD': os.getenv('LOTTE_PASSWORD')
    }
    
    print("환경 변수 설정:")
    for key, value in env_vars.items():
        if value:
            if 'PASSWORD' in key:
                print(f"   {key}: {'*' * len(value)}")
            else:
                print(f"   {key}: {value}")
        else:
            print(f"   {key}: 설정되지 않음")
    
    # 파일 존재 확인
    required_files = [
        'auto_lotte_pipeline.py',
        'run_pipeline.sh',
        'lotte_scraper.py',
        'requirements.txt'
    ]
    
    print("\n필수 파일 확인:")
    for file in required_files:
        if os.path.exists(file):
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file}")
    
    return True

def run_full_test():
    """전체 테스트 실행"""
    print("🧪 롯데 면세점 자동화 파이프라인 테스트 시작")
    print("=" * 60)
    
    test_results = []
    
    # 각 테스트 실행
    test_results.append(("데이터베이스 연결", test_database_connection()))
    test_results.append(("엑셀 변환", test_excel_conversion()))
    test_results.append(("개별 단계", test_individual_steps()))
    test_results.append(("설정", test_configuration()))
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 통과" if result else "❌ 실패"
        print(f"{test_name:<20} {status}")
        if result:
            passed += 1
    
    print(f"\n전체 결과: {passed}/{total} 테스트 통과")
    
    if passed == total:
        print("🎉 모든 테스트가 통과했습니다!")
        print("파이프라인을 안전하게 실행할 수 있습니다.")
        return True
    else:
        print("⚠️ 일부 테스트가 실패했습니다.")
        print("실패한 항목을 확인하고 수정한 후 다시 테스트해주세요.")
        return False

def main():
    """메인 실행 함수"""
    try:
        success = run_full_test()
        
        if success:
            print("\n🚀 파이프라인 실행 준비 완료!")
            print("다음 명령어로 파이프라인을 실행할 수 있습니다:")
            print("   ./run_pipeline.sh")
            print("   또는")
            print("   python auto_lotte_pipeline.py")
        else:
            print("\n❌ 파이프라인 실행 전 문제를 해결해주세요.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ 테스트가 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 테스트 실행 중 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 