#!/bin/bash
# AWS Mac 인스턴스에서 DbTest 프로젝트 설정 자동화 스크립트

echo "🍎 AWS Mac 인스턴스에서 DbTest 배포 시작..."

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 함수: 에러 체크
check_error() {
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ 오류 발생: $1${NC}"
        exit 1
    fi
}

# 함수: 성공 메시지
success_msg() {
    echo -e "${GREEN}✅ $1${NC}"
}

# 함수: 정보 메시지
info_msg() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# 함수: 경고 메시지
warn_msg() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# 1. Homebrew 설치 확인
info_msg "Homebrew 설치 확인 중..."
if ! command -v brew &> /dev/null; then
    warn_msg "Homebrew가 설치되지 않았습니다. 설치를 시작합니다..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    check_error "Homebrew 설치 실패"
    
    # PATH 업데이트 (Apple Silicon Mac인 경우)
    if [[ $(uname -m) == "arm64" ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    success_msg "Homebrew가 이미 설치되어 있습니다"
fi

# 2. 필수 도구 설치
info_msg "필수 도구들을 설치하는 중..."
brew update
brew install python@3.11 postgresql@14 tesseract tesseract-lang git
check_error "필수 도구 설치 실패"

# Python 심볼릭 링크 생성 (편의를 위해)
if ! command -v python3.11 &> /dev/null; then
    if [[ $(uname -m) == "arm64" ]]; then
        ln -sf /opt/homebrew/bin/python3.11 /usr/local/bin/python3.11
    fi
fi

success_msg "필수 도구 설치 완료"

# 3. PostgreSQL 시작
info_msg "PostgreSQL 서비스 시작 중..."
brew services start postgresql@14
check_error "PostgreSQL 시작 실패"
success_msg "PostgreSQL 서비스 시작됨"

# 4. 프로젝트 디렉토리 설정
PROJECT_DIR="$HOME/DbTest"
info_msg "프로젝트 디렉토리: $PROJECT_DIR"

if [ ! -d "$PROJECT_DIR" ]; then
    warn_msg "프로젝트 디렉토리가 없습니다. 생성합니다..."
    mkdir -p "$PROJECT_DIR"
fi

cd "$PROJECT_DIR"

# 5. Python 가상환경 설정
info_msg "Python 가상환경 설정 중..."
if [ ! -d "venv" ]; then
    python3.11 -m venv venv
    check_error "가상환경 생성 실패"
fi

source venv/bin/activate
check_error "가상환경 활성화 실패"

# pip 업그레이드
pip install --upgrade pip
success_msg "Python 가상환경 설정 완료"

# 6. Python 패키지 설치
info_msg "Python 패키지 설치 중..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    check_error "requirements.txt 설치 실패"
elif [ -f "requirements-prod.txt" ]; then
    pip install -r requirements-prod.txt
    check_error "requirements-prod.txt 설치 실패"
else
    warn_msg "requirements 파일을 찾을 수 없습니다. 수동으로 설치해주세요."
fi
success_msg "Python 패키지 설치 완료"

# 7. .env 파일 설정
info_msg ".env 파일 설정 중..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        success_msg ".env 파일이 .env.example에서 복사되었습니다"
    else
        # 기본 .env 파일 생성
        cat > .env << EOF
# Database
SQLALCHEMY_DATABASE_URL=postgresql://dbtest_user:dbtest_password@localhost:5432/dbtest_production

# OpenAI API
OPENAI_API_KEY_COMPANY=sk-your-openai-key-here

# JWT
SECRET_KEY=$(openssl rand -hex 32)
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Mac 환경 경로
STATIC_DIR=$PROJECT_DIR/static
UPLOADS_DIR=$PROJECT_DIR/uploads
TEMPLATES_DIR=$PROJECT_DIR/templates
TRANSLATIONS_DIR=$PROJECT_DIR/translations
EXCEL_TEMPLATE_DIR=$PROJECT_DIR/excel_template
EOF
        success_msg "기본 .env 파일이 생성되었습니다"
    fi
    
    warn_msg "⚠️  중요: .env 파일의 API 키와 데이터베이스 설정을 확인하세요!"
    echo "    파일 위치: $PROJECT_DIR/.env"
else
    success_msg ".env 파일이 이미 존재합니다"
fi

# 8. 데이터베이스 설정
info_msg "데이터베이스 설정 중..."

# PostgreSQL이 완전히 시작될 때까지 대기
sleep 5

# 데이터베이스 및 사용자 생성
createdb dbtest_production 2>/dev/null || true
createuser dbtest_user 2>/dev/null || true
psql -d postgres -c "ALTER USER dbtest_user PASSWORD 'dbtest_password';" 2>/dev/null || true
psql -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE dbtest_production TO dbtest_user;" 2>/dev/null || true

success_msg "데이터베이스 설정 완료"

# 9. 테이블 생성
info_msg "데이터베이스 테이블 생성 중..."
if [ -f "create_table.py" ]; then
    python create_table.py
    check_error "테이블 생성 실패"
    success_msg "데이터베이스 테이블 생성 완료"
else
    warn_msg "create_table.py 파일을 찾을 수 없습니다"
fi

# 10. 필요한 디렉토리 생성
info_msg "필요한 디렉토리 생성 중..."
mkdir -p uploads static templates translations excel_template logs
success_msg "디렉토리 생성 완료"

# 11. Tesseract 언어팩 확인
info_msg "Tesseract 언어팩 확인 중..."
if tesseract --list-langs | grep -q kor; then
    success_msg "한글 언어팩이 설치되어 있습니다"
else
    warn_msg "한글 언어팩이 설치되지 않았습니다. 추가 설치를 시도합니다..."
    brew install tesseract-lang
fi

# 12. LaunchDaemon 설정 (선택사항)
read -p "🤖 시스템 시작 시 자동으로 서비스를 시작하시겠습니까? (y/N): " AUTO_START

if [[ $AUTO_START =~ ^[Yy]$ ]]; then
    info_msg "LaunchDaemon 설정 중..."
    
    sudo tee /Library/LaunchDaemons/com.dbtest.app.plist > /dev/null << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.dbtest.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PROJECT_DIR/venv/bin/uvicorn</string>
        <string>app.main:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8000</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/app.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/error.log</string>
</dict>
</plist>
EOF
    
    sudo launchctl load /Library/LaunchDaemons/com.dbtest.app.plist
    success_msg "자동 시작 서비스가 설정되었습니다"
fi

# 13. 완료 메시지 및 다음 단계 안내
echo ""
echo "🎉 AWS Mac 인스턴스 배포 설정이 완료되었습니다!"
echo ""
echo "📋 다음 단계:"
echo "1. .env 파일 설정 확인:"
echo "   ${BLUE}nano $PROJECT_DIR/.env${NC}"
echo ""
echo "2. 개발 모드로 서버 시작:"
echo "   ${BLUE}cd $PROJECT_DIR${NC}"
echo "   ${BLUE}source venv/bin/activate${NC}"
echo "   ${BLUE}uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload${NC}"
echo ""
echo "3. 프로덕션 모드로 백그라운드 실행:"
echo "   ${BLUE}screen -S dbtest_app${NC}"
echo "   ${BLUE}cd $PROJECT_DIR && source venv/bin/activate${NC}"
echo "   ${BLUE}uvicorn app.main:app --host 0.0.0.0 --port 8000${NC}"
echo "   ${BLUE}# Ctrl+A, D로 분리${NC}"
echo ""
echo "4. 서비스 상태 확인:"
echo "   ${BLUE}curl http://localhost:8000${NC}"
echo ""
echo "🔗 서비스 접속: http://your-mac-instance-ip:8000"
echo ""

# 서비스 바로 시작 옵션
read -p "🚀 지금 바로 개발 서버를 시작하시겠습니까? (y/N): " START_NOW

if [[ $START_NOW =~ ^[Yy]$ ]]; then
    info_msg "개발 서버를 시작합니다..."
    echo "💡 서버를 중지하려면 Ctrl+C를 누르세요"
    sleep 2
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
fi 