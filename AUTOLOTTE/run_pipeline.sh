#!/bin/bash

# 롯데 면세점 자동화 파이프라인 실행 스크립트

echo "🚀 롯데 면세점 자동화 파이프라인 시작"
echo "=================================="

# 현재 디렉토리로 이동
cd "$(dirname "$0")"

# 가상환경 활성화 (있는 경우)
if [ -d "../venv" ]; then
    echo "🔧 가상환경 활성화 중..."
    source ../venv/bin/activate
fi

# 필요한 패키지 설치 확인
echo "📦 패키지 설치 확인 중..."
pip install -r requirements.txt

# 파이프라인 실행
echo "🔄 파이프라인 실행 중..."
python auto_lotte_pipeline.py

# 실행 결과 확인
if [ $? -eq 0 ]; then
    echo "✅ 파이프라인 성공적으로 완료되었습니다!"
else
    echo "❌ 파이프라인 실행 중 오류가 발생했습니다."
    exit 1
fi 