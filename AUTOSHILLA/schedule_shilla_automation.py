#!/usr/bin/env python3
"""
신라 자동화 스케줄러
매일 새벽 12시 1분에 실행
"""

import asyncio
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# 로깅 설정
def setup_logging():
    """로깅 설정"""
    # macOS EC2 인스턴스용 경로
    log_dir = Path("/Users/ec2-user/logs")
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"shilla_automation_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

async def run_shilla_automation():
    """신라 자동화 실행"""
    logger = setup_logging()
    
    try:
        logger.info("🚀 신라 자동화 스케줄러 시작!")
        logger.info(f"실행 시간: {datetime.now()}")
        
        # 현재 작업 디렉토리
        current_dir = "/Users/ec2-user/yido/yidoweb/dbtest/AUTOSHILLA"
        os.chdir(current_dir)
        
        # 가상환경 활성화
        venv_python = "/Users/ec2-user/yido/yidoweb/dbtest/venv/bin/python"
        if os.path.exists(venv_python):
            logger.info("가상환경 Python 사용")
            python_path = venv_python
        else:
            logger.info("시스템 Python 사용")
            python_path = sys.executable
        
        # shilla_automation.py 실행
        result = await asyncio.create_subprocess_exec(
            python_path, "shilla_automation.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await result.communicate()
        
        if result.returncode == 0:
            logger.info("✅ 신라 자동화 완료!")
            logger.info(f"출력: {stdout.decode()}")
        else:
            logger.error(f"❌ 신라 자동화 실패: {stderr.decode()}")
            
    except Exception as e:
        logger.error(f"❌ 스케줄러 실행 오류: {e}")

if __name__ == "__main__":
    asyncio.run(run_shilla_automation()) 
