# 🍎 AWS Mac 인스턴스 듀얼 프로젝트 배포 가이드

## 📋 프로젝트 구성

### 🔧 서비스 구성
- **fee_test**: 수수료 적용기준 관리 API (포트 8000)
- **DbTest**: 메인 애플리케이션 (포트 8001)

### 🌐 서비스 통신
- DbTest의 fee.html에서 fee_test API를 호출하여 수수료 데이터 관리
- 두 서비스는 독립적으로 실행되며 HTTP API로 통신

## 🚀 원클릭 배포

### 자동 배포 (권장)
```bash
# 1. 인스턴스 생성 및 자동 설정
./create-mac-instance-dual.sh

# 2. 모든 질문에 기본값(Enter) 또는 자동 배포 옵션(y) 선택
# 3. 완료 후 브라우저에서 접속
#    - fee_test API: http://YOUR_IP:8000
#    - DbTest 메인: http://YOUR_IP:8001
```

## 🔧 수동 배포

### 1단계: 인스턴스 생성
```bash
./create-mac-instance-dual.sh
```

### 2단계: 프로젝트 파일 업로드
```bash
# SSH 접속
ssh -i dbtest-mac-keypair.pem ec2-user@YOUR_IP

# 프로젝트 업로드 (로컬에서 실행)
scp -i dbtest-mac-keypair.pem -r ./DbTest/ ec2-user@YOUR_IP:~/DbTest/
scp -i dbtest-mac-keypair.pem -r ./fee_test/ ec2-user@YOUR_IP:~/fee_test/
```

### 3단계: 환경 설정
```bash
# SSH 접속 후 설정 스크립트 실행
chmod +x ~/DbTest/setup-mac-dual.sh
./DbTest/setup-mac-dual.sh
```

### 4단계: API 키 설정
```bash
nano ~/DbTest/.env
# OPENAI_API_KEY_COMPANY=sk-your-actual-key-here 수정
```

### 5단계: 서비스 시작
```bash
# 두 서비스 모두 시작
~/start_all_services.sh

# 또는 개별 시작
~/start_fee_test.sh    # 수수료 API (포트 8000)
~/start_dbtest.sh      # 메인 앱 (포트 8001)
```

## 📱 서비스 관리

### 상태 확인
```bash
# 실행 중인 서비스 확인
screen -list

# API 응답 확인
curl http://localhost:8000/health    # fee_test
curl http://localhost:8001           # DbTest

# 외부 접속 확인
curl http://YOUR_IP:8000/health
curl http://YOUR_IP:8001
```

### 로그 확인
```bash
# 개별 서비스 콘솔 접속
screen -r fee_test    # fee_test 로그
screen -r dbtest      # DbTest 로그

# 로그 파일 확인
tail -f ~/fee_test/logs/app.log    # fee_test 로그
tail -f ~/DbTest/logs/app.log      # DbTest 로그
```

### 서비스 중지/재시작
```bash
# 모든 서비스 중지
~/stop_all_services.sh

# 개별 서비스 중지
screen -S fee_test -X quit
screen -S dbtest -X quit

# 서비스 재시작
~/start_all_services.sh
```

## 🔗 접속 및 테스트

### 웹 브라우저 접속
```
# 메인 애플리케이션
http://YOUR_IP:8001

# 수수료 API 문서 (Swagger)
http://YOUR_IP:8000/docs
```

### 기능 테스트
1. **DbTest 메인 앱** (http://YOUR_IP:8001)
   - 로그인/회원가입 ✅
   - 파일 업로드 ✅
   - OCR 처리 ✅
   - 결과 확인 ✅

2. **수수료 관리** (DbTest의 /fee/ 페이지)
   - 템플릿 다운로드 ✅
   - 수수료 데이터 업로드 ✅
   - 수수료 기준 조회 ✅

3. **fee_test API** (http://YOUR_IP:8000)
   - API 문서 접근 ✅
   - 헬스 체크 ✅
   - 수수료 데이터 CRUD ✅

## 🛠️ 트러블슈팅

### 서비스 연결 오류
```bash
# 1. 포트 사용 확인
lsof -i :8000  # fee_test
lsof -i :8001  # DbTest

# 2. 서비스 재시작
~/stop_all_services.sh
~/start_all_services.sh

# 3. 개별 서비스 상태 확인
screen -r fee_test
screen -r dbtest
```

### API 통신 오류
```bash
# fee_test API 응답 확인
curl -v http://localhost:8000/health

# DbTest에서 fee_test 호출 확인
# 브라우저 개발자 도구 > Network 탭에서 API 호출 확인
```

### 데이터베이스 오류
```bash
# PostgreSQL 상태 확인
brew services list | grep postgresql

# 데이터베이스 재시작
brew services restart postgresql@14

# 테이블 재생성 (필요시)
cd ~/DbTest && source venv/bin/activate && python create_table.py
cd ~/fee_test && source venv/bin/activate && python create_table.py
```

## 🔧 개발 환경 설정

### 로컬 개발 시 주의사항
- **포트 충돌 방지**: fee_test(8000), DbTest(8001) 포트 분리
- **CORS 설정**: fee_test에서 모든 도메인 허용 설정됨
- **API URL**: fee.html에서 환경에 따른 동적 URL 설정

### 프로덕션 배포 시 고려사항
- **보안 그룹**: 8000, 8001 포트 모두 개방 필요
- **로드밸런서**: 필요시 ALB로 두 서비스 통합 가능
- **도메인 설정**: 서브도메인으로 서비스 분리 가능
  - api.yourdomain.com:8000 (fee_test)
  - app.yourdomain.com:8001 (DbTest)

## 🎯 성능 최적화

### 리소스 모니터링
```bash
# CPU/메모리 사용량
top
htop

# 디스크 사용량
df -h

# 네트워크 연결
netstat -tulpn | grep -E ':(8000|8001)'
```

### 로그 로테이션
```bash
# 로그 파일 크기 관리
find ~/DbTest/logs ~/fee_test/logs -name "*.log" -size +100M

# 자동 로그 정리 (크론 작업 설정 가능)
```

## 💡 유용한 팁

### 빠른 명령어 모음
```bash
# 서비스 상태 한 번에 확인
echo "=== Screen Sessions ===" && screen -list && echo "=== Port Usage ===" && lsof -i :8000 -i :8001

# 로그 실시간 모니터링
tail -f ~/fee_test/logs/app.log ~/DbTest/logs/app.log

# 서비스 재시작 원라이너
~/stop_all_services.sh && sleep 2 && ~/start_all_services.sh
```

### 백업 전략
```bash
# 데이터베이스 백업
pg_dump -U dbtest_user dbtest_production > backup_$(date +%Y%m%d_%H%M%S).sql

# 설정 파일 백업
tar -czf config_backup_$(date +%Y%m%d).tar.gz ~/DbTest/.env ~/fee_test/.env
```

---

## 📞 지원

문제 발생 시:
1. **로그 확인**: `screen -r [service_name]`
2. **포트 확인**: `lsof -i :8000` 및 `lsof -i :8001`
3. **서비스 재시작**: `~/stop_all_services.sh && ~/start_all_services.sh`
4. **데이터베이스 상태**: `brew services list | grep postgresql`

**⚠️ 중요**: 두 서비스가 모두 정상 동작해야 전체 시스템이 제대로 작동합니다. 