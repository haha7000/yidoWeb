#!/bin/bash
# EC2 Ubuntu에서 DbTest 프로젝트 설정 스크립트

echo "🚀 DbTest EC2 설정 시작..."

# 패키지 업데이트
sudo apt update && sudo apt upgrade -y

# Python 설치
sudo apt install python3-pip python3-venv python3-dev -y

# Tesseract OCR 및 한글 언어팩 설치
echo "📝 Tesseract OCR 설치 중..."
sudo apt install -y \
    tesseract-ocr \
    tesseract-ocr-kor \
    tesseract-ocr-eng \
    libtesseract-dev

# OpenCV 의존성 설치
echo "🖼️ OpenCV 의존성 설치 중..."
sudo apt install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgtk-3-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev

# PostgreSQL 클라이언트
sudo apt install postgresql-client -y

# Tesseract 설치 확인
echo "✅ Tesseract 설치 확인:"
tesseract --version
echo

echo "📋 사용 가능한 언어팩:"
tesseract --list-langs
echo

# 한글 언어팩 확인
if tesseract --list-langs | grep -q kor; then
    echo "✅ 한글 언어팩 설치됨"
else
    echo "❌ 한글 언어팩이 설치되지 않았습니다."
    echo "수동으로 설치: sudo apt install tesseract-ocr-kor"
fi

echo "🎯 EC2 기본 설정 완료!"
echo ""
echo "다음 단계:"
echo "1. 프로젝트 디렉토리로 이동"
echo "2. python3 -m venv venv"
echo "3. source venv/bin/activate"
echo "4. pip install -r requirements-prod.txt"
echo "5. .env 파일 설정"
echo "6. python create_table.py"
echo "7. uvicorn app.main:app --host 0.0.0.0 --port 8000" 