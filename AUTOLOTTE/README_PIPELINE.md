# 롯데 면세점 자동화 파이프라인 🚀

## 📋 개요

이 파이프라인은 롯데 면세점 매출 데이터를 자동으로 다운로드하고, 데이터 타입을 변환한 후 데이터베이스에 업로드하는 완전 자동화된 시스템입니다.

## 🔄 프로세스 흐름

```
1. 엑셀 데이터 다운로드 → 2. 데이터 타입 변환 → 3. DB 자동 업로드
```

### 1단계: 엑셀 데이터 다운로드 📥
- 롯데 면세점 시스템에 로그인
- 매출 데이터 조회 (상품별 → 브랜드별 폴백)
- 엑셀 파일로 저장

### 2단계: 데이터 타입 변환 🔄
- 다운로드된 엑셀 파일 분석
- PostgreSQL DB 스키마에 맞게 데이터 타입 변환
- 변환 성공률 검증

### 3단계: DB 자동 업로드 🗄️
- 변환된 데이터를 PostgreSQL에 배치 업로드
- 기존 데이터 확인 및 통계 제공

## 🛠️ 설치 및 설정

### 1. 의존성 설치
```bash
cd dbtest/AUTOLOTTE
pip install -r requirements.txt
```

### 2. 환경 변수 설정 (선택사항)
```bash
export LOTTE_DB_URL="postgresql://test_user:test_password@localhost:5432/my_test_db"
export LOTTE_USER_ID="T301912"
export LOTTE_PASSWORD="huixin210@"
```

## 🚀 사용 방법

### 방법 1: 쉘 스크립트 실행 (권장)
```bash
cd dbtest/AUTOLOTTE
./run_pipeline.sh
```

### 방법 2: Python 직접 실행
```bash
cd dbtest/AUTOLOTTE
python auto_lotte_pipeline.py
```

### 방법 3: 개별 단계 실행
```python
from auto_lotte_pipeline import LotteAutoPipeline

# 파이프라인 초기화
pipeline = LotteAutoPipeline()

# 1단계: 엑셀 다운로드
success = pipeline.step1_download_excel('T301912', 'huixin210@')

# 2단계: 데이터 타입 변환
if success:
    success = pipeline.step2_convert_data_types(verbose=True)

# 3단계: DB 업로드
if success:
    success = pipeline.step3_upload_to_db(batch_size=1000)
```

## 📁 파일 구조

```
dbtest/AUTOLOTTE/
├── auto_lotte_pipeline.py    # 메인 파이프라인 코드
├── run_pipeline.sh          # 실행 스크립트
├── README_PIPELINE.md       # 이 문서
├── lotte_pipeline.log       # 실행 로그 (자동 생성)
├── downloads/               # 다운로드된 엑셀 파일 저장소
│   └── lotte_sales_YYYYMMDD_HHMMSS.xlsx
├── main.py                  # 기존 다운로드 스크립트
├── lotte_scraper.py         # 기존 스크래퍼
└── requirements.txt         # 의존성 목록
```

## ⚙️ 설정 옵션

### 데이터베이스 연결
```python
# 기본 설정
db_url = "postgresql://test_user:test_password@localhost:5432/my_test_db"

# 환경 변수로 설정
export LOTTE_DB_URL="postgresql://user:pass@host:port/db"
```

### 배치 크기 조정
```python
# DB 업로드 시 배치 크기 (기본값: 1000)
pipeline.step3_upload_to_db(batch_size=500)
```

### 로그 레벨 조정
```python
# auto_lotte_pipeline.py에서 수정
logging.basicConfig(level=logging.DEBUG)  # 더 상세한 로그
```

## 📊 모니터링 및 로그

### 로그 파일
- `lotte_pipeline.log`: 상세한 실행 로그
- 콘솔 출력: 실시간 진행 상황

### 로그 예시
```
2024-01-15 10:30:00 - INFO - 🚀 롯데 면세점 자동화 파이프라인 시작
2024-01-15 10:30:01 - INFO - ✅ 데이터베이스 연결 및 테이블 생성 완료
2024-01-15 10:30:02 - INFO - 🔐 로그인 중...
2024-01-15 10:30:05 - INFO - 📊 매출 데이터 조회 중...
2024-01-15 10:30:10 - INFO - ✅ 엑셀 다운로드 완료: downloads/lotte_sales_20240115_103010.xlsx
2024-01-15 10:30:11 - INFO - 🔄 2단계: 데이터 타입 변환 시작
2024-01-15 10:30:15 - INFO - ✅ 데이터 타입 변환 완료 (성공률: 100.0%)
2024-01-15 10:30:16 - INFO - 🗄️ 3단계: DB 자동 업로드 시작
2024-01-15 10:30:20 - INFO - ✅ DB 업로드 완료: 1,234건 삽입됨
2024-01-15 10:30:20 - INFO - 🎉 전체 파이프라인 완료!
```

## 🔧 문제 해결

### 일반적인 오류

#### 1. 로그인 실패
```
❌ 로그인 실패
```
**해결방법:**
- 사용자 ID와 비밀번호 확인
- 롯데 면세점 시스템 접속 가능 여부 확인

#### 2. 데이터베이스 연결 실패
```
❌ 데이터베이스 연결 실패
```
**해결방법:**
- PostgreSQL 서비스 실행 확인
- 연결 정보 (URL, 사용자명, 비밀번호) 확인
- 방화벽 설정 확인

#### 3. 데이터 타입 변환 실패
```
❌ 데이터 타입 변환 실패 (성공률: 85.0%)
```
**해결방법:**
- 엑셀 파일 형식 확인
- `execl_test.py`로 개별 테스트
- 성공률이 90% 이상이어야 정상 처리

### 디버깅 모드
```python
# 상세한 디버그 정보 출력
pipeline.run_full_pipeline(verbose=True)
```

## 🔄 스케줄링

### Cron을 사용한 자동 실행
```bash
# 매일 새벽 1시에 실행
0 1 * * * cd /path/to/dbtest/AUTOLOTTE && ./run_pipeline.sh

# 매주 월요일 새벽 2시에 실행
0 2 * * 1 cd /path/to/dbtest/AUTOLOTTE && ./run_pipeline.sh
```

### systemd 서비스로 등록
```ini
# /etc/systemd/system/lotte-pipeline.service
[Unit]
Description=Lotte Duty Free Pipeline
After=network.target

[Service]
Type=oneshot
User=your_user
WorkingDirectory=/path/to/dbtest/AUTOLOTTE
ExecStart=/path/to/dbtest/AUTOLOTTE/run_pipeline.sh
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

## 📈 성능 최적화

### 배치 크기 조정
- 대용량 데이터: `batch_size=500`
- 소용량 데이터: `batch_size=2000`

### 메모리 사용량 최적화
- 엑셀 파일 처리 후 즉시 정리
- 배치 처리로 메모리 사용량 제한

## 🔒 보안 고려사항

### 민감 정보 관리
- 비밀번호는 환경 변수로 관리
- 로그 파일에 민감 정보 노출 방지
- 데이터베이스 연결 정보 암호화

### 접근 권한
- 실행 스크립트에 적절한 권한 설정
- 데이터베이스 사용자 권한 최소화

## 📞 지원

문제가 발생하면 다음을 확인해주세요:
1. 로그 파일 (`lotte_pipeline.log`) 확인
2. 각 단계별 개별 테스트
3. 데이터베이스 연결 상태 확인
4. 네트워크 연결 상태 확인

---

**버전:** 1.0.0  
**최종 업데이트:** 2024-01-15  
**작성자:** AI Assistant 