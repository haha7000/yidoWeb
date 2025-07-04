# 🍎 AWS Mac 인스턴스 듀얼 프로젝트 배포 - 실행 요약

## 📋 프로젝트 구성
- **fee_test**: 수수료 API (포트 8000)
- **DbTest**: 메인 앱 (포트 8001)

## 📋 준비사항
- AWS CLI 설치 및 설정
- OpenAI API 키
- DbTest와 fee_test 프로젝트

## 🚀 원클릭 배포

### 자동 배포 (5분)
```bash
# 1. 듀얼 프로젝트 인스턴스 생성 및 자동 설정
./create-mac-instance-dual.sh

# 2. 모든 질문에 기본값(Enter) 또는 자동 배포 옵션(y) 선택
# 3. 완료 후 브라우저에서 접속
#    - fee_test API: http://YOUR_IP:8000
#    - DbTest 메인: http://YOUR_IP:8001
```

## 🔧 수동 배포 (10분)

### 1단계: 인스턴스 생성
```bash
./create-mac-instance-dual.sh
```

### 2단계: 프로젝트 배포
```bash
# SSH 접속
ssh -i dbtest-mac-keypair.pem ec2-user@YOUR_IP

# 프로젝트 업로드 (로컬에서)
scp -i dbtest-mac-keypair.pem -r ./DbTest/ ec2-user@YOUR_IP:~/DbTest/
scp -i dbtest-mac-keypair.pem -r ./fee_test/ ec2-user@YOUR_IP:~/fee_test/

# 설정 스크립트 실행 (원격에서)
chmod +x ~/DbTest/setup-mac-dual.sh
./DbTest/setup-mac-dual.sh
```

### 3단계: API 키 설정
```bash
nano ~/DbTest/.env
# OPENAI_API_KEY_COMPANY=sk-your-actual-key-here 수정
```

### 4단계: 서비스 시작
```bash
# 두 서비스 모두 시작
~/start_all_services.sh
```

## 🎯 접속 확인
```
DbTest 메인: http://YOUR_IP:8001
fee_test API: http://YOUR_IP:8000
API 문서: http://YOUR_IP:8000/docs
```

## 📞 서비스 관리 명령어

### 상태 확인
```bash
screen -list                      # 실행 중인 서비스
curl http://localhost:8000/health # fee_test 상태
curl http://localhost:8001        # DbTest 상태
```

### 서비스 제어
```bash
~/start_all_services.sh          # 모든 서비스 시작
~/stop_all_services.sh           # 모든 서비스 중지
screen -r fee_test               # fee_test 콘솔
screen -r dbtest                 # DbTest 콘솔
```

### 로그 확인
```bash
tail -f ~/fee_test/logs/app.log  # fee_test 로그
tail -f ~/DbTest/logs/app.log    # DbTest 로그
```

### 인스턴스 관리
```bash
# 인스턴스 중지 (24시간 후)
aws ec2 stop-instances --instance-ids YOUR_INSTANCE_ID

# 인스턴스 시작
aws ec2 start-instances --instance-ids YOUR_INSTANCE_ID
```

## 🚨 긴급 명령어

### 서비스 재시작
```bash
~/stop_all_services.sh && sleep 2 && ~/start_all_services.sh
```

### 개별 서비스 수동 시작
```bash
# fee_test 수동 시작
cd ~/fee_test && source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000

# DbTest 수동 시작
cd ~/DbTest && source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### 포트 충돌 해결
```bash
# 포트 사용 확인
lsof -i :8000 -i :8001

# 프로세스 종료 (필요시)
kill -9 PID
```

---

## 📁 생성된 파일들

| 파일명 | 용도 |
|--------|------|
| `DUAL_PROJECT_DEPLOYMENT.md` | 상세 듀얼 배포 가이드 |
| `QUICK_START_DUAL.md` | 빠른 시작 가이드 |
| `create-mac-instance-dual.sh` | 듀얼 인스턴스 생성 스크립트 |
| `setup-mac-dual.sh` | 듀얼 환경 설정 스크립트 |

## 🔧 서비스 구성도

```
┌─────────────────────────────────────┐
│        AWS Mac Instance             │
├─────────────────────────────────────┤
│  fee_test API      │  DbTest Main   │
│  Port: 8000        │  Port: 8001    │
│  ┌──────────────┐  │  ┌───────────┐ │
│  │ FastAPI      │  │  │ FastAPI   │ │
│  │ 수수료 관리   │←─┼──│ 메인 앱   │ │
│  │ SQLAlchemy   │  │  │ OCR 처리  │ │
│  └──────────────┘  │  └───────────┘ │
└─────────────────────────────────────┘
           │
           ↓
  ┌─────────────────┐
  │   PostgreSQL    │
  │   Database      │
  └─────────────────┘
```

## ⚠️ 중요 사항
- **Mac 인스턴스는 24시간 최소 실행 정책 적용**
- **시간당 약 $1.08 요금 발생**
- **두 개의 포트(8000, 8001) 모두 개방 필요**
- **fee_test API가 정상 동작해야 DbTest의 수수료 기능 사용 가능**

🎉 **준비 완료!** 이제 `./create-mac-instance-dual.sh` 명령어로 듀얼 프로젝트 배포를 시작하세요! 