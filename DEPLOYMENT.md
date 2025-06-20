# AWS EC2 배포 가이드

## 📋 배포 전 체크리스트

### 1. **파일 준비**
```bash
# 프로젝트 압축 (venv 폴더 제외)
tar -czf DbTest.tar.gz --exclude='venv' --exclude='__pycache__' --exclude='.git' .
```

### 2. **EC2 인스턴스 요구사항**
- **OS**: Ubuntu 20.04 LTS 이상
- **메모리**: 최소 2GB (권장 4GB+)
- **스토리지**: 최소 20GB
- **인바운드 규칙**: 
  - SSH (22)
  - HTTP (80)
  - HTTPS (443)
  - 커스텀 포트 (8000) - 개발용

## 🚀 배포 단계

### Step 1: EC2 기본 설정
```bash
# 패키지 업데이트
sudo apt update && sudo apt upgrade -y

# Python 3.9+ 설치 확인
python3 --version
sudo apt install python3-pip python3-venv -y

# 시스템 의존성 설치
sudo apt install -y \
    postgresql-client \
    tesseract-ocr \
    tesseract-ocr-kor \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1
```

### Step 2: 프로젝트 설정
```bash
# 프로젝트 디렉토리 생성
mkdir -p /home/ubuntu/app
cd /home/ubuntu/app

# 압축 파일 업로드 후 압축 해제
tar -xzf DbTest.tar.gz

# 가상환경 생성
python3 -m venv venv
source venv/bin/activate

# 패키지 설치
pip install -r requirements-prod.txt
```

### Step 3: 환경변수 설정
```bash
# .env 파일 생성
cp .env.example .env
nano .env
```

**.env 파일 설정 예시:**
```env
# Database
SQLALCHEMY_DATABASE_URL=postgresql://username:password@localhost:5432/dbname

# OpenAI
OPENAI_API_KEY_COMPANY=sk-your-key-here

# JWT
SECRET_KEY=your-super-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Paths (EC2 환경)
STATIC_DIR=/home/ubuntu/app/static
UPLOADS_DIR=/home/ubuntu/app/uploads
TEMPLATES_DIR=/home/ubuntu/app/templates
TRANSLATIONS_DIR=/home/ubuntu/app/translations
EXCEL_TEMPLATE_DIR=/home/ubuntu/app/excel_template
```

### Step 4: 데이터베이스 설정
```bash
# PostgreSQL 설치 (필요한 경우)
sudo apt install postgresql postgresql-contrib -y

# 데이터베이스 생성
sudo -u postgres createdb your_db_name
sudo -u postgres createuser your_username
sudo -u postgres psql -c "ALTER USER your_username PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE your_db_name TO your_username;"

# 테이블 생성
cd /home/ubuntu/app
source venv/bin/activate
python create_table.py
```

### Step 5: 서비스 등록
```bash
# systemd 서비스 파일 생성
sudo nano /etc/systemd/system/dbtest.service
```

**서비스 파일 내용:**
```ini
[Unit]
Description=DbTest FastAPI application
After=network.target

[Service]
Type=exec
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/app
Environment=PATH=/home/ubuntu/app/venv/bin
ExecStart=/home/ubuntu/app/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 서비스 활성화
sudo systemctl daemon-reload
sudo systemctl enable dbtest
sudo systemctl start dbtest
sudo systemctl status dbtest
```

### Step 6: Nginx 설정 (선택사항)
```bash
# Nginx 설치
sudo apt install nginx -y

# 사이트 설정
sudo nano /etc/nginx/sites-available/dbtest
```

**Nginx 설정:**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /home/ubuntu/app/static/;
    }

    location /uploads/ {
        alias /home/ubuntu/app/uploads/;
    }
}
```

```bash
# 사이트 활성화
sudo ln -s /etc/nginx/sites-available/dbtest /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 🔧 트러블슈팅

### 1. **OpenCV 오류**
```bash
# 추가 의존성 설치
sudo apt install libopencv-dev python3-opencv -y
```

### 2. **PostgreSQL 연결 오류**
```bash
# PostgreSQL 상태 확인
sudo systemctl status postgresql
sudo systemctl start postgresql

# 방화벽 설정
sudo ufw allow 5432
```

### 3. **권한 오류**
```bash
# 디렉토리 권한 설정
sudo chown -R ubuntu:ubuntu /home/ubuntu/app
chmod -R 755 /home/ubuntu/app
```

### 4. **로그 확인**
```bash
# 서비스 로그
sudo journalctl -u dbtest -f

# Nginx 로그
sudo tail -f /var/log/nginx/error.log
```

## 📊 모니터링 및 유지보수

### 서비스 관리 명령어
```bash
# 서비스 상태 확인
sudo systemctl status dbtest

# 서비스 재시작
sudo systemctl restart dbtest

# 로그 실시간 모니터링
sudo journalctl -u dbtest -f

# 디스크 사용량 확인
df -h
du -sh /home/ubuntu/app/uploads/
```

### 백업 스크립트
```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump your_db_name > /home/ubuntu/backups/db_backup_$DATE.sql
tar -czf /home/ubuntu/backups/uploads_backup_$DATE.tar.gz /home/ubuntu/app/uploads/
```

## 🔒 보안 권장사항

1. **방화벽 설정**
```bash
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
```

2. **SSH 키 기반 인증 설정**
3. **정기적인 패키지 업데이트**
4. **데이터베이스 접근 제한**
5. **SSL/TLS 인증서 설정** (Let's Encrypt) 