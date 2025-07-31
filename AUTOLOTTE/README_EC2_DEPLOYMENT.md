# 롯데 면세점 자동화 파이프라인 EC2 배포 가이드

## 📋 개요
이 프로젝트는 롯데 면세점 매출 데이터를 자동으로 수집하여 PostgreSQL 데이터베이스에 저장하는 파이프라인입니다.

## 🚀 EC2 배포 방법

### 1. EC2 인스턴스 준비
- Ubuntu 20.04 LTS 이상 권장
- 최소 2GB RAM, 20GB 스토리지
- 보안 그룹에서 PostgreSQL 포트(5432) 열기

### 2. 프로젝트 파일 업로드
```bash
# EC2에 SSH 연결
ssh -i your-key.pem ubuntu@your-ec2-ip

# 프로젝트 파일들을 EC2에 업로드
scp -r /path/to/AUTOLOTTE/* ubuntu@your-ec2-ip:/home/ubuntu/yidoweb/dbtest/AUTOLOTTE/
```

### 3. 배포 스크립트 실행
```bash
# EC2에서 실행
cd /home/ubuntu/yidoweb/dbtest/AUTOLOTTE
chmod +x deploy_to_ec2.sh
./deploy_to_ec2.sh
```

## ⚙️ 서비스 관리

### 서비스 상태 확인
```bash
sudo systemctl status lotte-scheduler.service
```

### 서비스 시작/중지/재시작
```bash
sudo systemctl start lotte-scheduler.service
sudo systemctl stop lotte-scheduler.service
sudo systemctl restart lotte-scheduler.service
```

### 실시간 로그 확인
```bash
sudo journalctl -u lotte-scheduler.service -f
```

### 로그 파일 확인
```bash
# 일별 로그 파일
ls -la /home/ubuntu/yidoweb/dbtest/AUTOLOTTE/logs/
cat /home/ubuntu/yidoweb/dbtest/AUTOLOTTE/logs/scheduler_20241201.log
```

## 📅 스케줄 설정
- **실행 시간**: 매일 새벽 12시 1분 (00:01)
- **자동 재시작**: 서비스 중단 시 10초 후 자동 재시작
- **로그 관리**: 일별 로그 파일 생성

## 🗄️ 데이터베이스
- **DB**: PostgreSQL
- **데이터베이스명**: my_test_db
- **사용자**: test_user
- **비밀번호**: test_password
- **테이블**: lotte_excel_data

### DB 연결 확인
```bash
psql -h localhost -U test_user -d my_test_db -c "SELECT COUNT(*) FROM lotte_excel_data;"
```

## 🔧 문제 해결

### 1. 서비스가 시작되지 않는 경우
```bash
# 상세 로그 확인
sudo journalctl -u lotte-scheduler.service --no-pager

# 수동으로 스크립트 실행 테스트
cd /home/ubuntu/yidoweb/dbtest/AUTOLOTTE
python3 scheduler.py
```

### 2. 데이터베이스 연결 오류
```bash
# PostgreSQL 서비스 상태 확인
sudo systemctl status postgresql

# PostgreSQL 재시작
sudo systemctl restart postgresql
```

### 3. 권한 문제
```bash
# 파일 권한 확인 및 수정
sudo chown -R ubuntu:ubuntu /home/ubuntu/yidoweb/dbtest/AUTOLOTTE
chmod +x /home/ubuntu/yidoweb/dbtest/AUTOLOTTE/*.py
```

## 📊 모니터링

### 데이터 수집 현황 확인
```bash
# 최근 데이터 확인
psql -h localhost -U test_user -d my_test_db -c "
SELECT 
    DATE(매출일자) as 날짜,
    COUNT(*) as 데이터수,
    SUM(판매수량) as 총판매수량
FROM lotte_excel_data 
WHERE 매출일자 >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(매출일자)
ORDER BY 날짜 DESC;
"
```

### 브랜드별 통계
```bash
psql -h localhost -U test_user -d my_test_db -c "
SELECT 
    브랜드,
    COUNT(*) as 상품수,
    SUM(판매수량) as 총판매수량
FROM lotte_excel_data 
GROUP BY 브랜드 
ORDER BY 총판매수량 DESC 
LIMIT 10;
"
```

## 🔒 보안 고려사항
- 실제 운영 환경에서는 환경 변수로 민감한 정보 관리
- 데이터베이스 비밀번호 변경
- 방화벽 설정으로 외부 접근 제한
- 정기적인 로그 파일 정리

## 📞 지원
문제가 발생하면 로그 파일을 확인하고, 필요시 서비스를 재시작하세요. 