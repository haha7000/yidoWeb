#!/bin/bash

echo "롯데면세점 매출 데이터 자동 스케줄러 시작"
echo "====================================="

# Python 가상환경 활성화 (필요한 경우)
# source venv/bin/activate

# 패키지 설치
echo "필요한 패키지를 설치합니다..."
pip install -r requirements.txt

# 스케줄러 실행
echo "스케줄러를 시작합니다..."
python scheduler.py