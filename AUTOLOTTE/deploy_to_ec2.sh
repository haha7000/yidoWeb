#!/bin/bash

# 롯데 면세점 자동화 파이프라인 EC2 Mac 배포 스크립트

set -e  # 오류 발생 시 스크립트 중단

echo "🚀 롯데 면세점 자동화 파이프라인 EC2 Mac 배포 시작"

# 1. 기존 가상환경 활성화
echo "🐍 기존 가상환경 활성화 중..."
source /Users/ec2-user/yido/yidoweb/dbtest/venv/bin/activate

# 2. 프로젝트 디렉토리 설정
echo "📁 프로젝트 디렉토리 설정 중..."
cd /Users/ec2-user/yido/yidoweb/dbtest/AUTOLOTTE

# 3. 로그 디렉토리 생성
mkdir -p logs

# 4. 파일 권한 설정
echo "🔐 파일 권한 설정 중..."
chmod +x scheduler.py
chmod +x auto_lotte_pipeline.py

# 5. 실행 스크립트 생성
echo "📝 실행 스크립트 생성 중..."
cat > run_scheduler.sh << 'EOF'
#!/bin/bash
cd /Users/ec2-user/yido/yidoweb/dbtest/AUTOLOTTE
source /Users/ec2-user/yido/yidoweb/dbtest/venv/bin/activate
export PYTHONPATH=/Users/ec2-user/yido/yidoweb/dbtest
export LOTTE_DB_URL=postgresql://test_user:0000@localhost:5432/my_test_db
export LOTTE_USER_ID=T301912
export LOTTE_PASSWORD=huixin210@
python scheduler.py
EOF

chmod +x run_scheduler.sh

# 6. cron 작업 설정
echo "⏰ cron 작업 설정 중..."
# 기존 cron 작업 제거
crontab -l 2>/dev/null | grep -v "run_scheduler.sh" | crontab - 2>/dev/null || true

# 새 cron 작업 추가 (매일 새벽 12시 1분에 실행)
(crontab -l 2>/dev/null; echo "1 0 * * * /Users/ec2-user/yido/yidoweb/dbtest/AUTOLOTTE/run_scheduler.sh >> /Users/ec2-user/yido/yidoweb/dbtest/AUTOLOTTE/logs/cron.log 2>&1") | crontab -

# 7. 백그라운드에서 스케줄러 시작
echo "🚀 백그라운드 스케줄러 시작 중..."
# 기존 프로세스 종료
pkill -f "scheduler.py" 2>/dev/null || true

# nohup으로 백그라운드 실행
nohup ./run_scheduler.sh > logs/scheduler.log 2>&1 &
SCHEDULER_PID=$!

echo "✅ 배포 완료!"
echo ""
echo "📋 사용 가능한 명령어:"
echo "  ps aux | grep scheduler.py                    # 스케줄러 프로세스 확인"
echo "  tail -f logs/scheduler.log                    # 실시간 로그 확인"
echo "  tail -f logs/cron.log                         # cron 로그 확인"
echo "  crontab -l                                    # cron 작업 목록 확인"
echo "  crontab -e                                    # cron 작업 편집"
echo "  pkill -f scheduler.py                         # 스케줄러 프로세스 종료"
echo ""
echo "📅 스케줄: 매일 새벽 12시 1분에 자동 실행"
echo "📝 로그 위치: /Users/ec2-user/yido/yidoweb/dbtest/AUTOLOTTE/logs/"
echo "🐍 가상환경: /Users/ec2-user/yido/yidoweb/dbtest/venv"
echo "🔄 백그라운드 프로세스 PID: $SCHEDULER_PID"
echo ""
echo "🧪 즉시 테스트 실행:"
echo "  ./run_scheduler.sh" 

