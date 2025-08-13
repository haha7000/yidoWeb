#!/usr/bin/env python3
"""
사용자별 면세점 자동화 실행 스크립트
모든 활성화된 사용자 계정으로 자동화 실행
"""
import asyncio
import sys
import os
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.user_automation_service import automation_service

async def main():
    """메인 실행 함수"""
    print("🚀 사용자별 면세점 자동화 시작")
    print(f"⏰ 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        # 모든 자동화 실행
        result = await automation_service.run_all_automations()
        
        if result["success"]:
            print("\n✅ 자동화 실행 완료!")
            print(f"📊 실행 결과: {result['message']}")
            
            if "summary" in result:
                summary = result["summary"]
                print(f"   - 총 계정: {summary['total']}개")
                print(f"   - 성공: {summary['successful']}개")
                print(f"   - 실패: {summary['failed']}개")
            
            # 개별 결과 표시
            if result.get("results"):
                print("\n📋 개별 실행 결과:")
                for res in result["results"]:
                    status = "✅" if res["result"]["success"] else "❌"
                    duty_free = res["duty_free_type"].upper()
                    username = res["username"]
                    message = res["result"]["message"]
                    
                    print(f"   {status} {duty_free} - {username}: {message}")
                    
                    if res["result"]["success"] and "records_count" in res["result"]:
                        print(f"      └─ 처리된 레코드: {res['result']['records_count']}건")
        else:
            print(f"\n❌ 자동화 실행 실패: {result['message']}")
            return 1
        
        print("\n🏁 자동화 프로세스 종료")
        return 0
        
    except Exception as e:
        print(f"\n💥 예외 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())