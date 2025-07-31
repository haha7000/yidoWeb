#!/bin/bash
# 신라 스케줄러 시작 스크립트

echo "🚀 신라 엑셀 자동 다운로드 스케줄러 시작..."

# Docker Compose 명령어 확인 및 설정
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif command -v docker compose &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo "❌ Docker Compose를 찾을 수 없습니다."
    echo "다음 중 하나를 실행하세요:"
    echo "sudo curl -L \"https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose"
    echo "sudo chmod +x /usr/local/bin/docker-compose"
    exit 1
fi

echo "Using: $DOCKER_COMPOSE"

# 스케줄러 프로필로 실행
$DOCKER_COMPOSE --profile scheduler up -d shilla-scheduler

echo "✅ 스케줄러가 백그라운드에서 시작되었습니다."
echo "📋 로그 확인: $DOCKER_COMPOSE logs -f shilla-scheduler"
echo "🛑 중지: $DOCKER_COMPOSE --profile scheduler down"
