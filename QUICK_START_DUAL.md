# 🚀 AWS Mac 인스턴스 듀얼 프로젝트 빠른 배포

## 🎯 5분만에 배포하기

### 전제 조건
- AWS CLI 설치 및 설정 완료
- OpenAI API 키 준비
- DbTest와 fee_test 프로젝트 준비

### 1단계: 원클릭 배포 (5분)
```bash
# 자동 생성 및 배포 스크립트 실행
./create-mac-instance-dual.sh

# 모든 질문에 기본값(Enter)으로 응답
# 자동 배포 옵션 선택 (y)
```

### 2단계: 서비스 확인 (1분)
```bash
# 브라우저에서 접속
open http://YOUR_IP:8001    # DbTest 메인
open http://YOUR_IP:8000    # fee_test API

# 또는 터미널에서 확인
curl http://YOUR_IP:8000/health
curl http://YOUR_IP:8001
```

## 🔧 수동 배포 (10분)

### 1. 인스턴스 생성
```bash
./create-mac-instance-dual.sh
```

### 2. SSH 접속
```bash
ssh -i dbtest-mac-keypair.pem ec2-user@YOUR_IP
```

### 3. 프로젝트 업로드 (로컬에서)
```bash
# DbTest 프로젝트
scp -i dbtest-mac-keypair.pem -r ./DbTest/ ec2-user@YOUR_IP:~/DbTest/

# fee_test 프로젝트
scp -i dbtest-mac-keypair.pem -r ./fee_test/ ec2-user@YOUR_IP:~/fee_test/
```

### 4. 자동 설정 실행 (원격에서)
```bash
chmod +x ~/DbTest/setup-mac-dual.sh
./DbTest/setup-mac-dual.sh

# 모든 질문에 기본값으로 응답
# 마지막에 서버 시작 옵션 선택 (y)
```

### 5. API 키 설정
```bash
nano ~/DbTest/.env
# OPENAI_API_KEY_COMPANY=sk-your-actual-key-here 수정
```

### 6. 서비스 시작
```bash
# 두 서비스 모두 시작
~/start_all_services.sh
```

## ✅ 배포 완료 확인

### 🌐 웹 브라우저 테스트
```
메인 앱: http://YOUR_IP:8001
API 문서: http://YOUR_IP:8000/docs
```

### 🧪 기능 확인
1. **DbTest 메인 앱** ✅
   - 홈페이지 로딩
   - 회원가입/로그인
   - 파일 업로드
   - OCR 처리

2. **수수료 관리** ✅
   - 수수료 페이지 접근 (/fee/)
   - 템플릿 다운로드
   - 수수료 데이터 조회

3. **fee_test API** ✅
   - API 문서 접근
   - 헬스 체크 응답

## 🛠️ 유용한 명령어

### 서비스 관리
```bash
# 서비스 상태 확인
screen -list

# 개별 서비스 콘솔 접속
screen -r fee_test    # fee_test 콘솔
screen -r dbtest      # DbTest 콘솔

# 서비스 재시작
~/stop_all_services.sh
~/start_all_services.sh

# 로그 확인
tail -f ~/fee_test/logs/app.log
tail -f ~/DbTest/logs/app.log
```

### API 테스트
```bash
# fee_test API
curl http://localhost:8000/health
curl http://localhost:8000/docs

# DbTest API
curl http://localhost:8001
curl http://localhost:8001/health
```

### 포트 및 프로세스 확인
```bash
# 포트 사용 확인
lsof -i :8000  # fee_test
lsof -i :8001  # DbTest

# 프로세스 확인
ps aux | grep uvicorn
```

## 🚨 긴급 문제 해결

### 서비스가 안 되는 경우
```bash
# 1. 두 서비스 모두 재시작
~/stop_all_services.sh
sleep 3
~/start_all_services.sh

# 2. 개별 서비스 수동 시작
# Terminal 1: fee_test
cd ~/fee_test && source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2: DbTest
cd ~/DbTest && source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### SSH 접속 안 되는 경우
```bash
# 키 파일 권한 확인
chmod 400 dbtest-mac-keypair.pem

# 인스턴스 재시작
aws ec2 reboot-instances --instance-ids YOUR_INSTANCE_ID
```

### API 통신 오류
```bash
# fee_test 서비스 확인
curl -v http://localhost:8000/health

# 방화벽 확인 (AWS 보안 그룹)
# 8000, 8001 포트가 열려있는지 확인
```

### 데이터베이스 오류
```bash
# PostgreSQL 재시작
brew services restart postgresql@14

# 테이블 재생성
cd ~/DbTest && source venv/bin/activate && python create_table.py
cd ~/fee_test && source venv/bin/activate && python create_table.py  # 있는 경우
```

## 💡 성능 최적화

### 리소스 모니터링
```bash
# 시스템 리소스 확인
top
htop  # 설치된 경우

# 메모리 사용량
free -h

# 디스크 사용량
df -h
```

### 네트워크 최적화
```bash
# 연결 상태 확인
netstat -tulpn | grep -E ':(8000|8001)'

# 방화벽 상태 (macOS)
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate
```

## 🔗 외부 접속 URL

배포 완료 후 다음 URL로 접속:

| 서비스 | URL | 포트 | 용도 |
|--------|-----|------|------|
| DbTest 메인 | `http://YOUR_IP:8001` | 8001 | 메인 애플리케이션 |
| fee_test API | `http://YOUR_IP:8000` | 8000 | 수수료 관리 API |
| API 문서 | `http://YOUR_IP:8000/docs` | 8000 | Swagger 문서 |

## 📋 체크리스트

### 배포 완료 확인
- [ ] 인스턴스 생성 완료
- [ ] SSH 접속 가능
- [ ] 두 프로젝트 파일 업로드 완료
- [ ] 가상환경 설정 완료
- [ ] 데이터베이스 설정 완료
- [ ] OpenAI API 키 설정 완료
- [ ] fee_test 서비스 실행 중 (포트 8000)
- [ ] DbTest 서비스 실행 중 (포트 8001)
- [ ] 외부에서 두 서비스 접속 가능
- [ ] DbTest에서 수수료 기능 정상 동작

### 보안 확인
- [ ] 보안 그룹에서 필요한 포트만 개방
- [ ] SSH 키 파일 안전 보관
- [ ] .env 파일 보안 정보 확인

---

🎉 **축하합니다!** 

AWS Mac 인스턴스에 DbTest + fee_test 듀얼 프로젝트가 성공적으로 배포되었습니다!

이제 `http://YOUR_IP:8001`에서 메인 애플리케이션을 사용하실 수 있습니다. 