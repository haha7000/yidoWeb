# 🚀 EC2 즉시 실행 가이드

현재 EC2에서 `AppKit` 오류가 발생하는 문제를 해결하는 방법입니다.

## ⚡ 즉시 해결 방법

### 1. Tesseract OCR 설치
```bash
# EC2에서 실행
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-kor tesseract-ocr-eng libtesseract-dev
sudo apt install -y libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1
```

### 2. 수정된 파일들 적용
현재 프로젝트에 수정된 `ocr_module.py` 파일이 이미 크로스 플랫폼을 지원하도록 변경되었습니다:

- ✅ macOS에서는 Vision Framework 사용
- ✅ Linux에서는 Tesseract OCR 사용
- ✅ 자동 플랫폼 감지

### 3. 실행
```bash
cd ~/yido/DbTest
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 🧪 테스트

OCR 기능이 정상 작동하는지 확인:
```bash
python test_ocr.py
```

## 📋 예상 결과

### Linux (EC2)에서:
```
🔍 사용 가능한 OCR 엔진: Tesseract OCR
🖥️ 운영체제: Linux
```

### macOS (개발환경)에서:
```
🔍 사용 가능한 OCR 엔진: macOS Vision Framework
🖥️ 운영체제: Darwin
```

## 🔧 문제 해결

### Tesseract 버전 확인
```bash
tesseract --version
tesseract --list-langs
```

### 한글 언어팩 확인
```bash
# 한글(kor)이 목록에 있어야 함
tesseract --list-langs | grep kor
```

### 추가 의존성 설치 (필요시)
```bash
sudo apt install -y python3-opencv libopencv-dev
```

## ⚠️ 중요 사항

1. **macOS 개발환경**: 기존 Vision Framework 계속 사용
2. **Linux 배포환경**: 자동으로 Tesseract 사용
3. **성능 차이**: Tesseract는 Vision보다 느릴 수 있지만 정확도는 비슷
4. **언어 지원**: 한글 + 영어 모두 지원

## 🚀 최종 확인

서버가 정상 시작되면:
```
🔍 사용 가능한 OCR 엔진: Tesseract OCR
🖥️ 운영체제: Linux
✅ Tesseract OCR 사용 가능
INFO:     Uvicorn running on http://0.0.0.0:8000
```

이제 EC2에서 문제없이 실행될 것입니다! 🎉 