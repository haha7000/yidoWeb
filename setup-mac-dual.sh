#!/bin/bash
# AWS Mac 인스턴스에서 DbTest + fee_test 프로젝트 설정 자동화 스크립트

echo "🍎 AWS Mac 인스턴스에서 DbTest + fee_test 배포 시작..."

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
brew install python@3.11 postgresql@14 tesseract tesseract-lang git screen
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
DBTEST_DIR="$HOME/DbTest"
FEE_TEST_DIR="$HOME/fee_test"

info_msg "프로젝트 디렉토리: $DBTEST_DIR, $FEE_TEST_DIR"

# 디렉토리 생성
mkdir -p "$DBTEST_DIR" "$FEE_TEST_DIR"

# 5. DbTest 프로젝트 설정
info_msg "=== DbTest 프로젝트 설정 중 ==="
cd "$DBTEST_DIR"

if [ ! -d "venv" ]; then
    python3.11 -m venv venv
    check_error "DbTest 가상환경 생성 실패"
fi

source venv/bin/activate
pip install --upgrade pip

if [ -f "requirements-mac.txt" ]; then
    pip install -r requirements-mac.txt
    check_error "DbTest requirements-mac.txt 설치 실패"
elif [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    check_error "DbTest requirements.txt 설치 실패"
else
    warn_msg "DbTest requirements 파일을 찾을 수 없습니다"
fi

success_msg "DbTest Python 패키지 설치 완료"

# 6. fee_test 프로젝트 설정
info_msg "=== fee_test 프로젝트 설정 중 ==="
cd "$FEE_TEST_DIR"

if [ ! -d "venv" ]; then
    python3.11 -m venv venv
    check_error "fee_test 가상환경 생성 실패"
fi

source venv/bin/activate
pip install --upgrade pip

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    check_error "fee_test requirements.txt 설치 실패"
else
    warn_msg "fee_test requirements 파일을 찾을 수 없습니다"
fi

success_msg "fee_test Python 패키지 설치 완료"

# 7. DbTest .env 파일 설정
info_msg "DbTest .env 파일 설정 중..."
cd "$DBTEST_DIR"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        success_msg "DbTest .env 파일이 .env.example에서 복사되었습니다"
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
STATIC_DIR=$DBTEST_DIR/static
UPLOADS_DIR=$DBTEST_DIR/uploads
TEMPLATES_DIR=$DBTEST_DIR/templates
TRANSLATIONS_DIR=$DBTEST_DIR/translations
EXCEL_TEMPLATE_DIR=$DBTEST_DIR/excel_template
EOF
        success_msg "DbTest 기본 .env 파일이 생성되었습니다"
    fi
else
    success_msg "DbTest .env 파일이 이미 존재합니다"
fi

# 8. 데이터베이스 설정
info_msg "데이터베이스 설정 중..."
sleep 5

# 데이터베이스 및 사용자 생성
createdb dbtest_production 2>/dev/null || true
createuser dbtest_user 2>/dev/null || true
psql -d postgres -c "ALTER USER dbtest_user PASSWORD 'dbtest_password';" 2>/dev/null || true
psql -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE dbtest_production TO dbtest_user;" 2>/dev/null || true

success_msg "데이터베이스 설정 완료"

# 9. DbTest 테이블 생성
info_msg "DbTest 데이터베이스 테이블 생성 중..."
cd "$DBTEST_DIR"
if [ -f "create_table.py" ]; then
    source venv/bin/activate
    python create_table.py
    check_error "DbTest 테이블 생성 실패"
    success_msg "DbTest 데이터베이스 테이블 생성 완료"
else
    warn_msg "DbTest create_table.py 파일을 찾을 수 없습니다"
fi

# 10. fee_test 테이블 생성 (있는 경우)
info_msg "fee_test 데이터베이스 테이블 확인 중..."
cd "$FEE_TEST_DIR"
if [ -f "create_table.py" ]; then
    source venv/bin/activate
    python create_table.py
    check_error "fee_test 테이블 생성 실패"
    success_msg "fee_test 데이터베이스 테이블 생성 완료"
else
    info_msg "fee_test create_table.py 파일이 없습니다 (정상)"
fi

# 11. 필요한 디렉토리 생성
info_msg "필요한 디렉토리 생성 중..."
cd "$DBTEST_DIR"
mkdir -p uploads static templates translations excel_template logs
cd "$FEE_TEST_DIR"
mkdir -p logs
success_msg "디렉토리 생성 완료"

# 12. Tesseract 언어팩 확인
info_msg "Tesseract 언어팩 확인 중..."
if tesseract --list-langs | grep -q kor; then
    success_msg "한글 언어팩이 설치되어 있습니다"
else
    warn_msg "한글 언어팩이 설치되지 않았습니다. 추가 설치를 시도합니다..."
    brew install tesseract-lang
fi

# 13. 서비스 시작 스크립트 생성
info_msg "서비스 시작 스크립트 생성 중..."

# DbTest 시작 스크립트
cat > "$HOME/start_dbtest.sh" << 'EOF'
#!/bin/bash
cd ~/DbTest
source venv/bin/activate
echo "🚀 DbTest 서버 시작 중... (포트 8001)"
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
EOF

# fee_test 시작 스크립트
cat > "$HOME/start_fee_test.sh" << 'EOF'
#!/bin/bash
cd ~/fee_test
source venv/bin/activate
echo "🚀 fee_test 서버 시작 중... (포트 8000)"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
EOF

# 전체 서비스 시작 스크립트
cat > "$HOME/start_all_services.sh" << 'EOF'
#!/bin/bash
echo "🍎 두 서비스를 모두 시작합니다..."

# fee_test 서비스를 백그라운드에서 시작
echo "1. fee_test 서비스 시작 (포트 8000)..."
screen -dmS fee_test bash -c 'cd ~/fee_test && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000; exec bash'

sleep 3

# DbTest 서비스를 백그라운드에서 시작
echo "2. DbTest 서비스 시작 (포트 8001)..."
screen -dmS dbtest bash -c 'cd ~/DbTest && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8001; exec bash'

sleep 2

echo ""
echo "✅ 서비스 시작 완료!"
echo ""
echo "📋 실행 중인 서비스:"
echo "  - fee_test API: http://localhost:8000"
echo "  - DbTest 메인: http://localhost:8001"
echo ""
echo "🔍 서비스 상태 확인:"
echo "  screen -list"
echo ""
echo "📱 서비스 접속:"
echo "  screen -r fee_test    # fee_test 콘솔"
echo "  screen -r dbtest      # DbTest 콘솔"
echo ""
echo "🛑 서비스 중지:"
echo "  screen -S fee_test -X quit"
echo "  screen -S dbtest -X quit"
EOF

# 서비스 중지 스크립트
cat > "$HOME/stop_all_services.sh" << 'EOF'
#!/bin/bash
echo "🛑 모든 서비스를 중지합니다..."

screen -S fee_test -X quit 2>/dev/null
screen -S dbtest -X quit 2>/dev/null

echo "✅ 서비스 중지 완료!"
EOF

# 스크립트 실행 권한 부여
chmod +x "$HOME/start_dbtest.sh"
chmod +x "$HOME/start_fee_test.sh"
chmod +x "$HOME/start_all_services.sh"
chmod +x "$HOME/stop_all_services.sh"

success_msg "서비스 스크립트 생성 완료"

# 14. 완료 메시지 및 다음 단계 안내
echo ""
echo "🎉 AWS Mac 인스턴스 듀얼 프로젝트 배포 설정이 완료되었습니다!"
echo ""
echo "📋 다음 단계:"
echo "1. .env 파일 설정 확인:"
echo "   ${BLUE}nano $DBTEST_DIR/.env${NC}"
echo "   ${YELLOW}⚠️ OpenAI API 키를 반드시 설정하세요!${NC}"
echo ""
echo "2. 두 서비스 모두 시작:"
echo "   ${BLUE}~/start_all_services.sh${NC}"
echo ""
echo "3. 개별 서비스 시작:"
echo "   ${BLUE}~/start_fee_test.sh${NC}    # 수수료 API (포트 8000)"
echo "   ${BLUE}~/start_dbtest.sh${NC}      # 메인 앱 (포트 8001)"
echo ""
echo "4. 서비스 상태 확인:"
echo "   ${BLUE}screen -list${NC}"
echo "   ${BLUE}curl http://localhost:8000/health${NC}  # fee_test"
echo "   ${BLUE}curl http://localhost:8001${NC}         # DbTest"
echo ""
echo "5. 서비스 중지:"
echo "   ${BLUE}~/stop_all_services.sh${NC}"
echo ""
echo "🔗 외부 접속:"
echo "  - fee_test API: http://your-instance-ip:8000"
echo "  - DbTest 메인: http://your-instance-ip:8001"
echo ""

# 자동 시작 옵션
read -p "🚀 지금 바로 두 서비스를 모두 시작하시겠습니까? (y/N): " START_NOW

if [[ $START_NOW =~ ^[Yy]$ ]]; then
    warn_msg "⚠️ 시작하기 전에 .env 파일의 OpenAI API 키를 확인해주세요!"
    read -p "API 키를 설정했습니까? (y/N): " API_KEY_SET
    
    if [[ $API_KEY_SET =~ ^[Yy]$ ]]; then
        info_msg "두 서비스를 시작합니다..."
        ~/start_all_services.sh
    else
        warn_msg "먼저 API 키를 설정한 후 ~/start_all_services.sh를 실행하세요"
    fi
fi 