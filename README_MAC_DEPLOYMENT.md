# 🍎 AWS Mac 인스턴스 배포 - 실행 요약

## 📋 준비사항
- AWS CLI 설치 및 설정
- OpenAI API 키

## 🚀 원클릭 배포

### 자동 배포 (5분)
```bash
# 1. 인스턴스 생성 및 자동 설정
./create-mac-instance.sh

# 2. 모든 질문에 기본값(Enter) 또는 자동 배포 옵션(y) 선택
# 3. 완료 후 브라우저에서 접속
#    - DbTest 메인: http://YOUR_IP:8001
#    - fee_test API: http://YOUR_IP:8000
```

## 🔧 수동 배포 (10분)

### 1단계: 인스턴스 생성
```bash
./create-mac-instance.sh
```

### 2단계: 프로젝트 배포
```bash
# SSH 접속
ssh -i dbtest-mac-keypair.pem ec2-user@YOUR_IP

# 프로젝트 설정
git clone https://github.com/your-repo/DbTest.git
cd DbTest
chmod +x setup-mac.sh
./setup-mac.sh
```

### 3단계: API 키 설정
```bash
nano .env
# OPENAI_API_KEY_COMPANY=sk-your-actual-key-here 수정
```

### 4단계: 서비스 시작
```bash
# 듀얼 서비스 시작
~/start_all_services.sh

# 또는 개별 시작
~/start_fee_test.sh    # 수수료 API (포트 8000)
~/start_dbtest.sh      # 메인 앱 (포트 8001)
```

## 🎯 접속 확인
```
DbTest 메인: http://YOUR_IP:8001
fee_test API: http://YOUR_IP:8000
API 문서: http://YOUR_IP:8000/docs
```

## 📞 긴급 명령어

### 서비스 재시작
```bash
cd ~/DbTest && source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 로그 확인
```bash
tail -f ~/DbTest/logs/app.log
```

### 인스턴스 중지 (24시간 후)
```bash
aws ec2 stop-instances --instance-ids YOUR_INSTANCE_ID
```

---

## 📁 생성된 파일들

| 파일명 | 용도 |
|--------|------|
| `AWS_MAC_DEPLOYMENT.md` | 상세 배포 가이드 |
| `MAC_DEPLOYMENT_CHECKLIST.md` | 배포 체크리스트 |
| `QUICK_START_MAC.md` | 빠른 시작 가이드 |
| `create-mac-instance.sh` | 인스턴스 생성 스크립트 |
| `setup-mac.sh` | Mac 환경 설정 스크립트 |
| `requirements-mac.txt` | Mac용 Python 패키지 |

## ⚠️ 중요 사항
- **Mac 인스턴스는 24시간 최소 실행 정책 적용**
- **시간당 약 $1.08 요금 발생**
- **보안 그룹에서 8000 포트 개방 필요**

🎉 **준비 완료!** 이제 `./create-mac-instance.sh` 명령어로 배포를 시작하세요! 