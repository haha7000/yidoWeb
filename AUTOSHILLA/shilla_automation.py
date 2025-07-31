import asyncio
import subprocess
import sys
import os
from datetime import datetime

async def run_shilla_rpa():
    """신라 RPA 실행 (Excel 다운로드만)"""
    print("=== 1단계: 신라 웹사이트 자동화 시작 ===")
    try:
        # shilla_rpa.py 실행 (업로드 부분 제거된 버전)
        result = await asyncio.create_subprocess_exec(
            sys.executable, "shilla_rpa.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        
        if result.returncode == 0:
            print("✅ 신라 RPA 완료!")
            # stdout에서 다운로드된 파일 경로 추출 시도
            output = stdout.decode()
            print(f"RPA 출력: {output}")
            
            # 여러 가능한 메시지 확인
            if "엑셀 다운로드 완료" in output or "✅ 엑셀 다운로드 완료" in output:
                # 새로운 경로 반환 (프로젝트 내부 downloads 폴더)
                downloads_dir = os.path.join(os.path.dirname(__file__), 'downloads')
                excel_path = os.path.join(downloads_dir, 'shilla_report.xlsx')
                return excel_path
            
            # RPA가 성공했으면 파일이 존재할 가능성이 높음
            downloads_dir = os.path.join(os.path.dirname(__file__), 'downloads')
            excel_path = os.path.join(downloads_dir, 'shilla_report.xlsx')
            if os.path.exists(excel_path):
                print(f"✅ Excel 파일 발견: {excel_path}")
                return excel_path
            
            return None
        else:
            print(f"❌ 신라 RPA 실패: {stderr.decode()}")
            return None
            
    except Exception as e:
        print(f"❌ 신라 RPA 실행 오류: {e}")
        return None

async def run_excel_processor(excel_file_path):
    """Excel 처리 및 업로드 실행"""
    print("\n=== 2단계: Excel 처리 및 업로드 시작 ===")
    try:
        from excel_processor import process_and_upload_excel
        
        # 파일 존재 확인
        if not os.path.exists(excel_file_path):
            print(f"❌ Excel 파일이 존재하지 않습니다: {excel_file_path}")
            return False
        
        print(f"📁 Excel 파일 발견: {excel_file_path}")
        
        # Excel 처리 및 업로드 실행
        success = await process_and_upload_excel(excel_file_path)
        
        if success:
            print("✅ Excel 처리 및 업로드 완료!")
            return True
        else:
            print("❌ Excel 처리 및 업로드 실패")
            return False
            
    except Exception as e:
        print(f"❌ Excel 처리 실행 오류: {e}")
        return False

async def main():
    """메인 실행 함수"""
    print("🚀 신라 자동화 시스템 시작!")
    print(f"시작 시간: {datetime.now()}")
    
    # 1단계: 신라 RPA (Excel 다운로드)
    excel_file_path = await run_shilla_rpa()
    
    if not excel_file_path:
        print("❌ 1단계 실패로 중단")
        return
    
    # 2단계: Excel 처리 및 업로드
    excel_success = await run_excel_processor(excel_file_path)
    
    if excel_success:
        print("\n🎉 전체 프로세스 완료!")
    else:
        print("\n❌ 2단계 실패")
    
    print(f"종료 시간: {datetime.now()}")

if __name__ == "__main__":
    asyncio.run(main())
