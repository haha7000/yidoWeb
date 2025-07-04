# 🍎 AWS Mac 인스턴스 배포 체크리스트

## ✅ 배포 전 준비사항

### 로컬 환경 준비
- [ ] AWS CLI 설치 확인 (`aws --version`)
- [ ] AWS 자격 증명 설정 (`aws configure`)
- [ ] 프로젝트 파일 정리 (불필요한 파일 제거)
- [ ] .env.example 파일 준비
- [ ] OpenAI API 키 준비

### AWS 계정 확인
- [ ] AWS 계정에 Mac 인스턴스 생성 권한 확인
- [ ] Mac 인스턴스 지원 리전 확인 (us-east-1, us-west-2 등)
- [ ] 24시간 최소 실행 정책 이해
- [ ] 예상 비용 확인 (mac2.metal: ~$1.08/hour)

## 🚀 1단계: AWS Mac 인스턴스 생성

### 자동 생성 (권장)
```bash
# 인스턴스 생성 스크립트 실행
./create-mac-instance.sh
```

### 수동 생성
- [ ] EC2 콘솔에서 Mac 인스턴스 생성
- [ ] 키 페어 생성 및 다운로드
- [ ] 보안 그룹 설정 (SSH:22, HTTP:80, HTTPS:443, fee_test:8000, DbTest:8001)
- [ ] 인스턴스 시작 대기 (10-15분)

## 🚀 2단계: 프로젝트 배포

### 방법 1: 자동 배포
```bash
# SSH 접속
ssh -i dbtest-mac-keypair.pem ec2-user@YOUR_IP

# 프로젝트 업로드 (로컬에서)
scp -i dbtest-mac-keypair.pem -r ./ ec2-user@YOUR_IP:~/DbTest/

# 설정 스크립트 실행 (원격에서)
cd DbTest
chmod +x setup-mac.sh
./setup-mac.sh
```

### 방법 2: Git 클론
```bash
# SSH 접속
ssh -i dbtest-mac-keypair.pem ec2-user@YOUR_IP

# Git 클론
git clone https://github.com/your-username/DbTest.git
cd DbTest

# 설정 실행
chmod +x setup-mac.sh
./setup-mac.sh
```

## 🚀 3단계: 환경 설정

### .env 파일 설정
- [ ] OpenAI API 키 입력
- [ ] 데이터베이스 URL 확인
- [ ] JWT SECRET_KEY 확인
- [ ] 파일 경로 확인

```bash
nano .env
```

### 데이터베이스 확인
- [ ] PostgreSQL 서비스 실행 확인
- [ ] 데이터베이스 연결 테스트
- [ ] 테이블 생성 확인

```bash
# PostgreSQL 상태 확인
brew services list | grep postgresql

# 데이터베이스 연결 테스트
psql -h localhost -U dbtest_user -d dbtest_production
```

## 🚀 4단계: 서비스 실행

### 개발 모드 테스트
```bash
cd ~/DbTest
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 프로덕션 모드 실행
```bash
# Screen 세션 시작
screen -S dbtest_app
cd ~/DbTest
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Ctrl+A, D로 세션 분리
# screen -r dbtest_app로 다시 접속
```

## ✅ 4단계: 배포 확인

### 서비스 테스트
- [ ] 로컬 접속 테스트: `curl http://localhost:8000`
- [ ] 외부 접속 테스트: `curl http://YOUR_IP:8000`
- [ ] 웹 브라우저 접속: `http://YOUR_IP:8000`
- [ ] 로그인 기능 테스트
- [ ] 파일 업로드 기능 테스트

### 성능 확인
- [ ] CPU 사용률 확인: `top`
- [ ] 메모리 사용률 확인: `free -h`
- [ ] 디스크 공간 확인: `df -h`
- [ ] 네트워크 연결 확인: `netstat -tulpn | grep :8000`

## 🔧 트러블슈팅

### 일반적인 문제들

#### SSH 연결 불가
- [ ] 키 파일 권한 확인: `chmod 400 keypair.pem`
- [ ] 보안 그룹에서 SSH(22) 포트 열림 확인
- [ ] 인스턴스가 완전히 부팅되었는지 확인 (10-15분 소요)

#### 웹 서비스 접속 불가
- [ ] FastAPI 서비스 실행 상태 확인
- [ ] 8000 포트 사용 확인: `lsof -i :8000`
- [ ] 보안 그룹에서 8000 포트 열림 확인
- [ ] 방화벽 설정 확인

#### 데이터베이스 연결 오류
- [ ] PostgreSQL 서비스 상태 확인
- [ ] .env 파일의 데이터베이스 URL 확인
- [ ] 데이터베이스 권한 확인

#### Python 패키지 오류
- [ ] 가상환경 활성화 확인
- [ ] requirements-mac.txt 사용 확인
- [ ] 패키지 재설치: `pip install -r requirements-mac.txt`

## 📱 모니터링 및 관리

### 로그 확인
```bash
# 애플리케이션 로그
tail -f ~/DbTest/logs/app.log

# 에러 로그
tail -f ~/DbTest/logs/error.log

# 시스템 로그
tail -f /var/log/system.log
```

### 자동 시작 설정
- [ ] LaunchDaemon 설정 확인
- [ ] 재부팅 테스트
- [ ] 자동 시작 동작 확인

### 백업 계획
- [ ] 데이터베이스 백업 스크립트 설정
- [ ] 업로드 파일 백업 계획
- [ ] 설정 파일 백업

## 💰 비용 관리

### 중요 사항
- [ ] **24시간 최소 실행 정책 확인**
- [ ] 사용하지 않을 때 인스턴스 중지 계획
- [ ] CloudWatch로 비용 모니터링 설정
- [ ] 불필요한 리소스 정리

### 비용 절약 팁
- [ ] 개발 완료 후 즉시 인스턴스 중지
- [ ] EBS 볼륨 최적화
- [ ] 불필요한 스냅샷 삭제
- [ ] 사용하지 않는 보안 그룹 정리

## 🎯 완료 체크

배포가 성공적으로 완료되면:

- [ ] 웹 브라우저에서 `http://YOUR_IP:8000` 접속 가능
- [ ] 로그인/회원가입 기능 정상 동작
- [ ] 파일 업로드 기능 정상 동작
- [ ] OCR 처리 기능 정상 동작
- [ ] 데이터베이스 저장 기능 정상 동작
- [ ] 인스턴스 정보 파일 저장 완료

## 📞 지원 및 문의

문제가 발생하면:
1. 로그 파일 확인
2. 트러블슈팅 가이드 참조
3. AWS 문서 확인
4. 필요시 AWS 지원팀 문의

---

**⚠️ 중요 안내**: Mac 인스턴스는 24시간 최소 실행 정책이 있으므로, 배포 전 이를 충분히 고려하시기 바랍니다. 