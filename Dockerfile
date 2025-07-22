# Python 3.11 베이스 이미지 사용 (ARM64 지원)
FROM python:3.11

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 설치 (OCR, 이미지 처리 등에 필요)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Docker 전용 requirements.txt 복사 및 패키지 설치
COPY requirements-docker.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# 정적 파일 및 업로드 디렉토리 생성
RUN mkdir -p static uploads templates translations excel_template

# 포트 노출
EXPOSE 8001

# FastAPI 실행 (uvicorn) - 포트 8001로 수정
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]