#!/usr/bin/env python3
"""
롯데 면세점 자동화 파이프라인 스케줄러
매일 새벽 12시 1분에 실행
"""

import os
import sys
import time
import logging
import schedule
import subprocess
from datetime import datetime
from pathlib import Path

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).parent
os.chdir(PROJECT_ROOT)

# 로깅 설정
log_dir = PROJECT_ROOT / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / f'scheduler_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_pipeline():
    """파이프라인 실행 함수"""
    logger.info("🚀 롯데 면세점 파이프라인 실행 시작")
    
    try:
        # auto_lotte_pipeline.py 실행
        result = subprocess.run([
            sys.executable, "auto_lotte_pipeline.py"
        ], capture_output=True, text=True, timeout=3600)  # 1시간 타임아웃
        
        if result.returncode == 0:
            logger.info("✅ 파이프라인 실행 성공")
            logger.info(f"출력: {result.stdout}")
        else:
            logger.error(f"❌ 파이프라인 실행 실패 (코드: {result.returncode})")
            logger.error(f"오류: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        logger.error("❌ 파이프라인 실행 타임아웃 (1시간 초과)")
    except Exception as e:
        logger.error(f"❌ 파이프라인 실행 중 오류: {e}")

def setup_schedule():
    """스케줄 설정"""
    # 매일 새벽 12시 1분에 실행
    schedule.every().day.at("00:01").do(run_pipeline)
    
    logger.info("📅 스케줄 설정 완료: 매일 새벽 12시 1분")
    logger.info("🔄 스케줄러 시작...")

def main():
    """메인 함수"""
    logger.info("🚀 롯데 면세점 자동화 스케줄러 시작")
    logger.info(f"📁 작업 디렉토리: {PROJECT_ROOT}")
    logger.info(f"📝 로그 디렉토리: {log_dir}")
    
    # 스케줄 설정
    setup_schedule()
    
    # 즉시 한 번 실행 (테스트용)
    logger.info("🧪 초기 테스트 실행...")
    run_pipeline()
    
    # 스케줄 루프
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # 1분마다 체크
        except KeyboardInterrupt:
            logger.info("⏹️ 스케줄러 종료 요청됨")
            break
        except Exception as e:
            logger.error(f"❌ 스케줄러 오류: {e}")
            time.sleep(60)  # 오류 발생 시 1분 대기 후 재시도

if __name__ == "__main__":
    main()