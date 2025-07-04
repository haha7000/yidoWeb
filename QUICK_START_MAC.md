# 🚀 AWS Mac 인스턴스 빠른 배포 가이드

## 🎯 5분만에 배포하기

### 전제 조건
- AWS CLI 설치 및 설정 완료
- OpenAI API 키 준비

### 1단계: 인스턴스 생성 (5분)
```bash
# 자동 생성 스크립트 실행
./create-mac-instance.sh

# 모든 질문에 기본값(Enter)으로 응답
# 또는 자동 배포 옵션 선택 (y)
```

### 2단계: 서비스 확인 (1분)
```bash
# 브라우저에서 접속
open http://YOUR_IP:8000

# 또는 터미널에서 확인
curl http://YOUR_IP:8000
```

## 🔧 수동 배포 (10분)

### 1. 인스턴스 생성
```bash
./create-mac-instance.sh
```

### 2. SSH 접속
```bash
ssh -i dbtest-mac-keypair.pem ec2-user@YOUR_IP
```

### 3. 프로젝트 설정
```bash
# Git 클론 (추천)
git clone https://github.com/your-repo/DbTest.git
cd DbTest

# 또는 로컬에서 파일 업로드
# scp -i dbtest-mac-keypair.pem -r ./ ec2-user@YOUR_IP:~/DbTest/
```

### 4. 자동 설정 실행
```bash
chmod +x setup-mac.sh
./setup-mac.sh

# 모든 질문에 기본값으로 응답
# 마지막에 서버 시작 옵션 선택 (y)
```

### 5. .env 파일 수정
```bash
nano .env

# 다음 내용 수정:
OPENAI_API_KEY_COMPANY=sk-your-actual-api-key-here
```

### 6. 서비스 재시작
```bash
# 개발 모드
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 또는 프로덕션 모드 (백그라운드)
screen -S dbtest
uvicorn app.main:app --host 0.0.0.0 --port 8000
# Ctrl+A, D로 분리
```

## ✅ 배포 완료 확인

### 웹 브라우저 테스트
```
http://YOUR_IP:8000
```

### 기능 확인
1. **홈페이지 로딩** ✅
2. **회원가입/로그인** ✅  
3. **파일 업로드** ✅
4. **OCR 처리** ✅

## 🛠️ 유용한 명령어

### 서비스 관리
```bash
# 서비스 상태 확인
curl http://localhost:8000

# 프로세스 확인
ps aux | grep uvicorn

# 포트 사용 확인
lsof -i :8000

# 로그 확인
tail -f ~/DbTest/logs/app.log
```

### 데이터베이스 관리
```bash
# PostgreSQL 상태
brew services list | grep postgresql

# 데이터베이스 접속
psql -U dbtest_user -d dbtest_production
```

### 인스턴스 관리
```bash
# 인스턴스 중지 (24시간 후에만)
aws ec2 stop-instances --instance-ids i-1234567890abcdef0

# 인스턴스 시작
aws ec2 start-instances --instance-ids i-1234567890abcdef0

# 인스턴스 상태 확인
aws ec2 describe-instances --instance-ids i-1234567890abcdef0
```

## 🚨 긴급 문제 해결

### 서비스가 안 되는 경우
```bash
# 1. 서비스 재시작
cd ~/DbTest
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2. 포트 충돌 해결
sudo lsof -i :8000
kill -9 PID

# 3. 패키지 재설치
pip install -r requirements-mac.txt
```

### SSH 접속 안 되는 경우
```bash
# 키 파일 권한 확인
chmod 400 dbtest-mac-keypair.pem

# 인스턴스 재시작 (AWS CLI)
aws ec2 reboot-instances --instance-ids YOUR_INSTANCE_ID
```

### 데이터베이스 오류
```bash
# PostgreSQL 재시작
brew services restart postgresql@14

# 데이터베이스 재생성
dropdb dbtest_production
createdb dbtest_production
python create_table.py
```

## 💡 성능 최적화

### 메모리 사용량 확인
```bash
# 시스템 리소스 확인
top
htop  # 설치된 경우

# Python 프로세스 메모리
ps aux | grep python
```

### 로그 로테이션
```bash
# 로그 파일 크기 제한
logrotate /etc/logrotate.conf
```

## 📞 지원

### 문제 발생 시 수집할 정보
1. 인스턴스 ID
2. 에러 로그 (`~/DbTest/logs/error.log`)
3. 시스템 로그
4. 네트워크 상태

### 유용한 링크
- [AWS Mac Instance 문서](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-mac-instances.html)
- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [PostgreSQL 문서](https://www.postgresql.org/docs/)

---

🎉 **축하합니다!** AWS Mac 인스턴스에 성공적으로 배포되었습니다! 