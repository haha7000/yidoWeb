# 🎉 AWS Mac 인스턴스 듀얼 프로젝트 배포 - 최종 요약

## 🚀 배포 준비 완료!

### 🔧 프로젝트 구성
| 서비스 | 포트 | 역할 | 실행 명령어 |
|--------|------|------|-------------|
| **fee_test** | 8000 | 수수료 관리 API | `uvicorn main:app --host 0.0.0.0 --port 8000 --reload` |
| **DbTest** | 8001 | 메인 애플리케이션 | `uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload` |

### 🌐 서비스 통신
- DbTest의 `fee.html`에서 fee_test API를 자동으로 호출
- localhost와 AWS 환경 모두 지원하는 동적 URL 설정 완료

## 📁 생성된 배포 파일들

### 🔧 자동화 스크립트
| 파일명 | 용도 | 실행 권한 |
|--------|------|----------|
| `create-mac-instance-dual.sh` | AWS Mac 인스턴스 생성 | ✅ |
| `setup-mac-dual.sh` | 듀얼 프로젝트 환경 설정 | ✅ |

### 📖 배포 가이드
| 파일명 | 내용 | 대상 |
|--------|------|------|
| `DUAL_PROJECT_DEPLOYMENT.md` | 상세 배포 가이드 | 개발자 |
| `QUICK_START_DUAL.md` | 빠른 시작 가이드 | 빠른 배포 |
| `README_DUAL_DEPLOYMENT.md` | 실행 명령어 요약 | 레퍼런스 |

### ⚙️ 환경별 설정
| 파일명 | 용도 | 환경 |
|--------|------|------|
| `requirements-mac.txt` | Mac 전용 패키지 | AWS Mac |
| `templates/fee.html` | localhost/AWS 자동 인식 | 수정됨 |

## 🚀 원클릭 배포 시작

### 1. 인스턴스 생성 및 배포
```bash
# 모든 설정을 자동으로 처리
./create-mac-instance-dual.sh

# 질문에 대한 응답:
# - 리전: Enter (기본값: us-east-1)
# - 인스턴스 타입: Enter (기본값: mac2.metal)
# - 자동 배포: y (예)
```

### 2. 완료 후 접속
```bash
# 메인 애플리케이션
open http://YOUR_IP:8001

# API 문서
open http://YOUR_IP:8000/docs
```

## 🔧 수동 배포 (세부 제어 필요시)

### 단계별 실행
```bash
# 1. 인스턴스 생성
./create-mac-instance-dual.sh

# 2. SSH 접속
ssh -i dbtest-mac-keypair.pem ec2-user@YOUR_IP

# 3. 프로젝트 업로드 (로컬에서)
scp -i dbtest-mac-keypair.pem -r ./DbTest/ ec2-user@YOUR_IP:~/DbTest/
scp -i dbtest-mac-keypair.pem -r ./fee_test/ ec2-user@YOUR_IP:~/fee_test/

# 4. 환경 설정 (원격에서)
chmod +x ~/DbTest/setup-mac-dual.sh
./DbTest/setup-mac-dual.sh

# 5. API 키 설정
nano ~/DbTest/.env
# OPENAI_API_KEY_COMPANY=sk-your-key-here

# 6. 서비스 시작
~/start_all_services.sh
```

## 🛠️ 서비스 관리

### 기본 명령어
```bash
# 상태 확인
screen -list
curl http://localhost:8000/health  # fee_test
curl http://localhost:8001         # DbTest

# 서비스 제어
~/start_all_services.sh    # 모든 서비스 시작
~/stop_all_services.sh     # 모든 서비스 중지

# 개별 콘솔 접속
screen -r fee_test         # fee_test 콘솔
screen -r dbtest           # DbTest 콘솔

# 로그 확인
tail -f ~/fee_test/logs/app.log
tail -f ~/DbTest/logs/app.log
```

### 트러블슈팅
```bash
# 포트 충돌 확인
lsof -i :8000 -i :8001

# 서비스 재시작
~/stop_all_services.sh && sleep 2 && ~/start_all_services.sh

# 데이터베이스 재시작
brew services restart postgresql@14

# 테이블 재생성
cd ~/DbTest && source venv/bin/activate && python create_table.py
cd ~/fee_test && source venv/bin/activate && python create_table.py
```

## ✅ 배포 검증 체크리스트

### AWS 인스턴스
- [ ] Mac 인스턴스 생성 완료
- [ ] SSH 접속 가능
- [ ] 보안 그룹에서 8000, 8001 포트 개방

### 프로젝트 설정
- [ ] DbTest 프로젝트 업로드 완료
- [ ] fee_test 프로젝트 업로드 완료
- [ ] 가상환경 설정 완료
- [ ] PostgreSQL 설치 및 실행

### 서비스 실행
- [ ] fee_test API 서비스 실행 중 (포트 8000)
- [ ] DbTest 메인 서비스 실행 중 (포트 8001)
- [ ] 외부에서 두 서비스 접속 가능

### 기능 테스트
- [ ] DbTest 홈페이지 로딩 ✅
- [ ] 회원가입/로그인 기능 ✅
- [ ] 파일 업로드 및 OCR 처리 ✅
- [ ] 수수료 관리 페이지 접근 ✅
- [ ] fee_test API 문서 접근 ✅

## 🔗 접속 URL

배포 완료 후 사용 가능한 URL:

| 서비스 | URL | 설명 |
|--------|-----|------|
| **메인 앱** | `http://YOUR_IP:8001` | DbTest 애플리케이션 |
| **수수료 API** | `http://YOUR_IP:8000` | fee_test API |
| **API 문서** | `http://YOUR_IP:8000/docs` | Swagger 문서 |
| **수수료 관리** | `http://YOUR_IP:8001/fee/` | 수수료 기능 |

## 💰 비용 안내

### AWS Mac 인스턴스 요금
- **mac2.metal**: 시간당 약 $1.08
- **24시간 최소 실행**: 중간에 중지해도 24시간 요금 청구
- **월 예상 비용**: 약 $800 (24시간 연속 실행 시)

### 비용 최적화 팁
- 개발 완료 후 즉시 인스턴스 중지
- 24시간 후 중지하여 추가 요금 방지
- 필요시 스팟 인스턴스 고려 (가능한 경우)

## 🎯 성공 시나리오

1. **개발팀**: 빠른 프로토타입 배포 및 테스트
2. **데모**: 클라이언트에게 실제 환경에서 시연
3. **QA**: 실제 환경에서 통합 테스트
4. **마이그레이션**: 기존 시스템에서 새 환경으로 이전

## 📞 지원 및 문의

### 문제 발생 시 확인 순서
1. **로그 확인**: `screen -r [service_name]`
2. **포트 상태**: `lsof -i :8000 -i :8001`
3. **서비스 재시작**: `~/stop_all_services.sh && ~/start_all_services.sh`
4. **DB 상태**: `brew services list | grep postgresql`

### 즉시 해결이 필요한 경우
```bash
# 응급 복구 명령어 (원라이너)
~/stop_all_services.sh && sleep 3 && brew services restart postgresql@14 && sleep 5 && ~/start_all_services.sh
```

---

## 🎉 축하합니다!

**AWS Mac 인스턴스에 DbTest + fee_test 듀얼 프로젝트 배포가 완전히 준비되었습니다!**

이제 `./create-mac-instance-dual.sh` 명령어 하나로 전체 시스템을 배포할 수 있습니다.

### 🚀 지금 시작하세요!
```bash
./create-mac-instance-dual.sh
```

**행운을 빕니다! 🍀** 