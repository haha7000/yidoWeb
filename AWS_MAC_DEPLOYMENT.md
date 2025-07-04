# AWS Mac 인스턴스 배포 가이드

## 📋 배포 전 준비사항

### AWS Mac 인스턴스 요구사항
- **인스턴스 타입**: mac1.metal 또는 mac2.metal
- **OS**: macOS Big Sur 11.7+ 또는 macOS Monterey 12.6+
- **메모리**: 최소 32GB (Mac1), 8GB (Mac2.medium)
- **스토리지**: 최소 50GB
- **보안 그룹 설정**:
  - SSH (22)
  - HTTP (80) 
  - HTTPS (443)
  - 커스텀 포트 (8000) - fee_test API
  - 커스텀 포트 (8001) - DbTest 메인 앱

## 🚀 1단계: Mac 인스턴스 설정

### SSH 접속
```bash
# Mac 인스턴스에 SSH 접속
ssh -i your-key.pem ec2-user@your-mac-instance-ip
```

### 기본 개발 도구 설치
```bash
# Homebrew 설치 (없는 경우)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 필수 도구 설치
brew install python@3.11 postgresql@14 tesseract tesseract-lang

# Python 가상환경 도구
brew install pipenv

# Git 설정 (필요한 경우)
brew install git
```

## 🚀 2단계: 프로젝트 배포

### 프로젝트 클론 또는 업로드
```bash
# 방법 1: Git 클론 (권장)
cd ~
git clone your-repository-url DbTest
cd DbTest

# 방법 2: 로컬에서 압축 파일 업로드
# 로컬에서: tar -czf DbTest.tar.gz --exclude='venv' --exclude='__pycache__' --exclude='.git' .
# scp -i your-key.pem DbTest.tar.gz ec2-user@your-mac-instance-ip:~/
# tar -xzf DbTest.tar.gz
# cd DbTest
```

### Python 가상환경 설정
```bash
# Python 3.11 사용
python3.11 -m venv venv
source venv/bin/activate

# Mac용 requirements 설치
pip install --upgrade pip
pip install -r requirements.txt
```

## 🚀 3단계: 환경 설정

### 환경변수 파일 설정
```bash
# .env 파일 생성
cp .env.example .env
nano .env
```

**.env 파일 설정 (Mac 환경)**:
```env
# Database (PostgreSQL)
SQLALCHEMY_DATABASE_URL=postgresql://username:password@localhost:5432/dbname

# OpenAI API
OPENAI_API_KEY_COMPANY=sk-your-openai-key-here

# JWT 설정
SECRET_KEY=your-super-secret-jwt-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Mac 환경 경로 설정
STATIC_DIR=/Users/ec2-user/DbTest/static
UPLOADS_DIR=/Users/ec2-user/DbTest/uploads
TEMPLATES_DIR=/Users/ec2-user/DbTest/templates
TRANSLATIONS_DIR=/Users/ec2-user/DbTest/translations
EXCEL_TEMPLATE_DIR=/Users/ec2-user/DbTest/excel_template
```

### PostgreSQL 설정
```bash
# PostgreSQL 서비스 시작
brew services start postgresql@14

# 데이터베이스 생성
createdb dbtest_production
createuser dbtest_user
psql -c "ALTER USER dbtest_user PASSWORD 'your_secure_password';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE dbtest_production TO dbtest_user;"

# 테이블 생성
cd ~/DbTest
source venv/bin/activate
python create_table.py
```

## 🚀 4단계: 서비스 실행

### 개발 모드 실행
```bash
# fee_test API 서버 (포트 8000)
cd ~/fee_test
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &

# DbTest 메인 서버 (포트 8001)
cd ~/DbTest
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 프로덕션 모드 (데몬화)
```bash
# screen 설치
brew install screen

# fee_test API 서비스 시작
screen -dmS fee_test bash -c 'cd ~/fee_test && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000; exec bash'

# DbTest 메인 서비스 시작
screen -dmS dbtest bash -c 'cd ~/DbTest && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8001; exec bash'

# 세션 확인
screen -list

# 개별 세션 접속
# screen -r fee_test     # fee_test 콘솔
# screen -r dbtest       # DbTest 콘솔
```

### LaunchDaemon 사용 (자동 시작)
```bash
# plist 파일 생성
sudo nano /Library/LaunchDaemons/com.dbtest.app.plist
```

**plist 파일 내용**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.dbtest.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/ec2-user/DbTest/venv/bin/uvicorn</string>
        <string>app.main:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8000</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/ec2-user/DbTest</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/ec2-user/DbTest/logs/app.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/ec2-user/DbTest/logs/error.log</string>
</dict>
</plist>
```

```bash
# 로그 디렉토리 생성
mkdir -p ~/DbTest/logs

# 서비스 등록 및 시작
sudo launchctl load /Library/LaunchDaemons/com.dbtest.app.plist
sudo launchctl start com.dbtest.app
```

## 🚀 5단계: Nginx 설정 (선택사항)

### Nginx 설치 및 설정
```bash
# Nginx 설치
brew install nginx

# 설정 파일 생성
sudo nano /usr/local/etc/nginx/nginx.conf
```

**Nginx 설정**:
```nginx
events {
    worker_connections 1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;

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
            alias /Users/ec2-user/DbTest/static/;
        }

        location /uploads/ {
            alias /Users/ec2-user/DbTest/uploads/;
        }
    }
}
```

```bash
# Nginx 시작
brew services start nginx
```

## 🔧 Mac 환경 특화 트러블슈팅

### 1. **Python 경로 이슈**
```bash
# Python 3.11 경로 확인
which python3.11
/usr/local/bin/python3.11

# 가상환경에서 올바른 Python 사용 확인
source venv/bin/activate
which python
```

### 2. **Tesseract 언어팩**
```bash
# 한글 언어팩 설치 확인
tesseract --list-langs | grep kor

# 없는 경우 수동 설치
brew install tesseract-lang
```

### 3. **PostgreSQL 연결 오류**
```bash
# PostgreSQL 상태 확인
brew services list | grep postgres

# 재시작
brew services restart postgresql@14
```

### 4. **포트 사용 확인**
```bash
# 포트 8000 사용 확인
lsof -i :8000

# 프로세스 종료 (필요한 경우)
kill -9 PID
```

### 5. **방화벽 설정**
```bash
# macOS 방화벽 상태 확인
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate

# 필요한 경우 포트 허용 (AWS 보안 그룹이 더 중요)
```

## 📱 배포 확인

### 서비스 동작 확인
```bash
# 로컬에서 확인
curl http://localhost:8001

# 외부에서 확인
curl http://your-mac-instance-ip:8001
```

### 로그 확인
```bash
# 애플리케이션 로그
tail -f ~/DbTest/logs/app.log

# Nginx 로그 (사용하는 경우)
tail -f /usr/local/var/log/nginx/access.log
```

## 🎯 자동화 스크립트

Mac 배포를 위한 자동화 스크립트도 만들어드릴까요? 