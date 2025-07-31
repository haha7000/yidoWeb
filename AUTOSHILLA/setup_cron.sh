#!/bin/bash

# 신라 자동화 Cron 작업 설정 스크립트 (macOS EC2 인스턴스용)

echo "🚀 신라 자동화 Cron 작업 설정 시작..."

# 현재 사용자 확인
CURRENT_USER=$(whoami)
echo "현재 사용자: $CURRENT_USER"

# 현재 작업 디렉토리 설정
WORK_DIR="/Users/$CURRENT_USER/yido/yidoweb/dbtest/AUTOSHILLA"
echo "작업 디렉토리: $WORK_DIR"

# ========================================
# 🕐 스케줄 시간 설정 (여기서 변경하세요!)
# ========================================
# 형식: "분 시 * * *" (매일 실행)
# 예시:
# "10 0 * * *"     = 매일 새벽 12시 10분 (00:10)
# "30 1 * * *"     = 매일 새벽 1시 30분 (01:30)
# "0 2 * * *"      = 매일 새벽 2시 정각 (02:00)
# "15 6 * * *"     = 매일 아침 6시 15분 (06:15)
# "45 23 * * *"    = 매일 밤 11시 45분 (23:45)

# 원하는 시간으로 변경하세요!
SCHEDULE_TIME="38 9 * * *"  # 기본값: 매일 새벽 12시 10분

echo "📅 설정된 스케줄 시간: $SCHEDULE_TIME"

# 로그 디렉토리 생성
mkdir -p "/Users/$CURRENT_USER/logs"
echo "✅ 로그 디렉토리 생성 완료"

# 가상환경 Python 경로 확인
VENV_PYTHON="$WORK_DIR/venv/bin/python"
if [ -f "$VENV_PYTHON" ]; then
    PYTHON_PATH="$VENV_PYTHON"
    echo "✅ 가상환경 Python 사용: $PYTHON_PATH"
else
    # 시스템 Python 경로 확인 (macOS용)
    PYTHON_PATH=$(which python3)
    if [ -z "$PYTHON_PATH" ]; then
        PYTHON_PATH=$(which python)
    fi
    echo "⚠️ 시스템 Python 사용: $PYTHON_PATH"
fi

# 기존 cron 작업에서 중복된 신라 자동화 작업 제거
echo "기존 cron 작업 정리 중..."
TEMP_CRON=$(mktemp)
crontab -l 2>/dev/null | grep -v "schedule_shilla_automation.py" | grep -v "rpaTest.*schedule_shilla_automation.py" > "$TEMP_CRON"

# 새로운 Cron 작업 추가 (설정된 시간에 실행)
CRON_JOB="$SCHEDULE_TIME cd $WORK_DIR && $PYTHON_PATH schedule_shilla_automation.py >> /Users/$CURRENT_USER/logs/cron.log 2>&1"

echo "추가할 Cron 작업:"
echo "$CRON_JOB"

# 기존 cron 작업 확인
echo "현재 cron 작업:"
cat "$TEMP_CRON"

# 새로운 cron 작업 추가
(cat "$TEMP_CRON"; echo "$CRON_JOB") | crontab -

# 임시 파일 삭제
rm "$TEMP_CRON"

echo "✅ Cron 작업 설정 완료!"
echo ""
echo "설정된 작업 확인:"
crontab -l

echo ""
echo "📋 다음 명령어로 로그 확인 가능:"
echo "tail -f /Users/$CURRENT_USER/logs/cron.log"
echo "tail -f /Users/$CURRENT_USER/logs/shilla_automation_$(date +%Y%m%d).log" 
