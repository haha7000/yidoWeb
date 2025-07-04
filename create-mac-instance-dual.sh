#!/bin/bash
# AWS CLI를 사용해 Mac 인스턴스 생성 및 DbTest + fee_test 배포 스크립트

echo "🍎 AWS Mac 인스턴스 생성 및 듀얼 프로젝트 배포 시작..."

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 함수 정의
check_error() {
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ 오류 발생: $1${NC}"
        exit 1
    fi
}

success_msg() {
    echo -e "${GREEN}✅ $1${NC}"
}

info_msg() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

warn_msg() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# 설정 변수들
INSTANCE_NAME="DbTest-FeeTest-Mac-Instance"
KEY_PAIR_NAME="dbtest-mac-keypair"
SECURITY_GROUP_NAME="dbtest-mac-sg"
IMAGE_ID=""  # 자동으로 최신 macOS AMI 선택
INSTANCE_TYPE="mac2.metal"  # 또는 mac1.metal
REGION="us-east-1"  # Mac 인스턴스가 지원되는 리전

# 1. AWS CLI 설치 확인
info_msg "AWS CLI 설치 확인 중..."
if ! command -v aws &> /dev/null; then
    warn_msg "AWS CLI가 설치되지 않았습니다. 설치해주세요:"
    echo "  brew install awscli"
    echo "  또는 https://aws.amazon.com/cli/"
    exit 1
else
    success_msg "AWS CLI가 설치되어 있습니다"
fi

# 2. AWS 자격 증명 확인
info_msg "AWS 자격 증명 확인 중..."
if ! aws sts get-caller-identity &> /dev/null; then
    warn_msg "AWS 자격 증명이 설정되지 않았습니다. 설정해주세요:"
    echo "  aws configure"
    exit 1
else
    AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
    success_msg "AWS 자격 증명 확인됨 (계정: $AWS_ACCOUNT)"
fi

# 3. 리전 설정
read -p "AWS 리전을 입력하세요 (기본값: us-east-1): " USER_REGION
REGION=${USER_REGION:-$REGION}

aws configure set default.region $REGION
info_msg "리전이 $REGION 로 설정되었습니다"

# 4. Mac 인스턴스 타입 선택
echo "Mac 인스턴스 타입을 선택하세요:"
echo "1. mac2.metal (M2, 8 vCPU, 32GB RAM) - 권장"
echo "2. mac1.metal (Intel, 12 vCPU, 32GB RAM)"
read -p "선택 (1-2, 기본값: 1): " INSTANCE_CHOICE

case $INSTANCE_CHOICE in
    2)
        INSTANCE_TYPE="mac1.metal"
        ;;
    *)
        INSTANCE_TYPE="mac2.metal"
        ;;
esac

info_msg "인스턴스 타입: $INSTANCE_TYPE"

# 5. 최신 macOS AMI 찾기
info_msg "최신 macOS AMI 검색 중..."
if [[ $INSTANCE_TYPE == "mac2.metal" ]]; then
    IMAGE_ID=$(aws ec2 describe-images \
        --owners amazon \
        --filters "Name=name,Values=amzn-ec2-macos-*" \
                  "Name=architecture,Values=arm64" \
        --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
        --output text)
else
    IMAGE_ID=$(aws ec2 describe-images \
        --owners amazon \
        --filters "Name=name,Values=amzn-ec2-macos-*" \
                  "Name=architecture,Values=x86_64" \
        --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
        --output text)
fi

if [ "$IMAGE_ID" == "None" ] || [ -z "$IMAGE_ID" ]; then
    warn_msg "macOS AMI를 찾을 수 없습니다. 리전을 확인해주세요."
    exit 1
fi

success_msg "macOS AMI 찾음: $IMAGE_ID"

# 6. 키 페어 생성 또는 확인
info_msg "키 페어 확인 중..."
if aws ec2 describe-key-pairs --key-names $KEY_PAIR_NAME &> /dev/null; then
    success_msg "키 페어 '$KEY_PAIR_NAME'가 이미 존재합니다"
else
    info_msg "새 키 페어 생성 중..."
    aws ec2 create-key-pair \
        --key-name $KEY_PAIR_NAME \
        --query 'KeyMaterial' \
        --output text > ${KEY_PAIR_NAME}.pem
    check_error "키 페어 생성 실패"
    
    chmod 400 ${KEY_PAIR_NAME}.pem
    success_msg "키 페어가 생성되었습니다: ${KEY_PAIR_NAME}.pem"
fi

# 7. 보안 그룹 생성
info_msg "보안 그룹 설정 중..."
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query 'Vpcs[0].VpcId' --output text)

# 보안 그룹이 이미 있는지 확인
if aws ec2 describe-security-groups --group-names $SECURITY_GROUP_NAME &> /dev/null; then
    SECURITY_GROUP_ID=$(aws ec2 describe-security-groups --group-names $SECURITY_GROUP_NAME --query 'SecurityGroups[0].GroupId' --output text)
    success_msg "보안 그룹 '$SECURITY_GROUP_NAME'가 이미 존재합니다 ($SECURITY_GROUP_ID)"
else
    # 새 보안 그룹 생성
    SECURITY_GROUP_ID=$(aws ec2 create-security-group \
        --group-name $SECURITY_GROUP_NAME \
        --description "Security group for DbTest + fee_test Mac instance" \
        --vpc-id $VPC_ID \
        --query 'GroupId' \
        --output text)
    check_error "보안 그룹 생성 실패"
    
    # 보안 그룹 규칙 추가
    aws ec2 authorize-security-group-ingress \
        --group-id $SECURITY_GROUP_ID \
        --protocol tcp \
        --port 22 \
        --cidr 0.0.0.0/0 \
        --description "SSH access"
    
    aws ec2 authorize-security-group-ingress \
        --group-id $SECURITY_GROUP_ID \
        --protocol tcp \
        --port 80 \
        --cidr 0.0.0.0/0 \
        --description "HTTP access"
    
    aws ec2 authorize-security-group-ingress \
        --group-id $SECURITY_GROUP_ID \
        --protocol tcp \
        --port 443 \
        --cidr 0.0.0.0/0 \
        --description "HTTPS access"
    
    aws ec2 authorize-security-group-ingress \
        --group-id $SECURITY_GROUP_ID \
        --protocol tcp \
        --port 8000 \
        --cidr 0.0.0.0/0 \
        --description "fee_test API"
    
    aws ec2 authorize-security-group-ingress \
        --group-id $SECURITY_GROUP_ID \
        --protocol tcp \
        --port 8001 \
        --cidr 0.0.0.0/0 \
        --description "DbTest application"
    
    success_msg "보안 그룹이 생성되었습니다: $SECURITY_GROUP_ID"
fi

# 8. Mac 인스턴스 생성
info_msg "Mac 인스턴스 생성 중... (이 과정은 몇 분이 걸릴 수 있습니다)"

INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $IMAGE_ID \
    --count 1 \
    --instance-type $INSTANCE_TYPE \
    --key-name $KEY_PAIR_NAME \
    --security-group-ids $SECURITY_GROUP_ID \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
    --query 'Instances[0].InstanceId' \
    --output text)

check_error "인스턴스 생성 실패"
success_msg "Mac 인스턴스가 생성되었습니다: $INSTANCE_ID"

# 9. 인스턴스 상태 확인
info_msg "인스턴스 시작을 기다리는 중..."
aws ec2 wait instance-running --instance-ids $INSTANCE_ID
check_error "인스턴스 시작 대기 실패"

# 10. 퍼블릭 IP 주소 가져오기
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

success_msg "인스턴스가 준비되었습니다!"
echo ""
echo "📋 인스턴스 정보:"
echo "  - 인스턴스 ID: $INSTANCE_ID"
echo "  - 인스턴스 타입: $INSTANCE_TYPE"
echo "  - 퍼블릭 IP: $PUBLIC_IP"
echo "  - 키 파일: ${KEY_PAIR_NAME}.pem"
echo ""

# 11. SSH 연결 대기
info_msg "SSH 서비스 시작을 기다리는 중... (macOS 부팅에 시간이 걸릴 수 있습니다)"
echo "이 과정은 5-10분 정도 걸릴 수 있습니다..."

# SSH 연결 가능할 때까지 대기
while ! ssh -i ${KEY_PAIR_NAME}.pem -o ConnectTimeout=10 -o StrictHostKeyChecking=no ec2-user@$PUBLIC_IP "echo 'SSH 연결 성공'" &> /dev/null; do
    echo -n "."
    sleep 30
done

echo ""
success_msg "SSH 연결이 가능합니다!"

# 12. 자동 배포 옵션
echo ""
echo "🚀 다음 단계:"
echo ""
echo "1. SSH로 인스턴스 접속:"
echo "   ${BLUE}ssh -i ${KEY_PAIR_NAME}.pem ec2-user@$PUBLIC_IP${NC}"
echo ""
echo "2. 프로젝트 파일 업로드:"
echo "   ${BLUE}# DbTest 프로젝트${NC}"
echo "   ${BLUE}scp -i ${KEY_PAIR_NAME}.pem -r ./DbTest/ ec2-user@$PUBLIC_IP:~/DbTest/${NC}"
echo "   ${BLUE}# fee_test 프로젝트${NC}"
echo "   ${BLUE}scp -i ${KEY_PAIR_NAME}.pem -r ./fee_test/ ec2-user@$PUBLIC_IP:~/fee_test/${NC}"
echo ""
echo "3. 설정 스크립트 실행:"
echo "   ${BLUE}chmod +x ~/DbTest/setup-mac-dual.sh && ~/DbTest/setup-mac-dual.sh${NC}"
echo ""

read -p "🤖 지금 바로 프로젝트를 업로드하고 설정하시겠습니까? (y/N): " AUTO_DEPLOY

if [[ $AUTO_DEPLOY =~ ^[Yy]$ ]]; then
    info_msg "프로젝트 업로드 중..."
    
    # 현재 디렉토리에서 DbTest 프로젝트 확인
    if [ -d "./DbTest" ]; then
        info_msg "DbTest 프로젝트 업로드 중..."
        tar -czf dbtest-project.tar.gz \
            --exclude='venv' \
            --exclude='__pycache__' \
            --exclude='.git' \
            --exclude='*.pyc' \
            --exclude='uploads/*' \
            --exclude='logs/*' \
            -C ./DbTest .
        
        scp -i ${KEY_PAIR_NAME}.pem dbtest-project.tar.gz ec2-user@$PUBLIC_IP:~/
        check_error "DbTest 프로젝트 업로드 실패"
        
        ssh -i ${KEY_PAIR_NAME}.pem ec2-user@$PUBLIC_IP "mkdir -p ~/DbTest && tar -xzf ~/dbtest-project.tar.gz -C ~/DbTest/"
        rm -f dbtest-project.tar.gz
    else
        warn_msg "현재 디렉토리에 DbTest 폴더가 없습니다. 수동으로 업로드해주세요."
    fi
    
    # fee_test 프로젝트 확인
    if [ -d "./fee_test" ]; then
        info_msg "fee_test 프로젝트 업로드 중..."
        tar -czf fee-test-project.tar.gz \
            --exclude='venv' \
            --exclude='__pycache__' \
            --exclude='.git' \
            --exclude='*.pyc' \
            --exclude='logs/*' \
            --exclude='node_modules' \
            -C ./fee_test .
        
        scp -i ${KEY_PAIR_NAME}.pem fee-test-project.tar.gz ec2-user@$PUBLIC_IP:~/
        check_error "fee_test 프로젝트 업로드 실패"
        
        ssh -i ${KEY_PAIR_NAME}.pem ec2-user@$PUBLIC_IP "mkdir -p ~/fee_test && tar -xzf ~/fee-test-project.tar.gz -C ~/fee_test/"
        rm -f fee-test-project.tar.gz
    else
        warn_msg "현재 디렉토리에 fee_test 폴더가 없습니다. 수동으로 업로드해주세요."
    fi
    
    # 설정 스크립트 업로드 및 실행
    if [ -f "./setup-mac-dual.sh" ]; then
        scp -i ${KEY_PAIR_NAME}.pem ./setup-mac-dual.sh ec2-user@$PUBLIC_IP:~/
        ssh -i ${KEY_PAIR_NAME}.pem ec2-user@$PUBLIC_IP "chmod +x ~/setup-mac-dual.sh && ~/setup-mac-dual.sh"
    else
        warn_msg "setup-mac-dual.sh 파일이 없습니다. 수동으로 설정해주세요."
    fi
    
    success_msg "자동 배포가 완료되었습니다!"
    echo ""
    echo "🔗 서비스 접속:"
    echo "  - fee_test API: http://$PUBLIC_IP:8000"
    echo "  - DbTest 메인: http://$PUBLIC_IP:8001"
fi

# 인스턴스 정보를 파일로 저장
cat > mac-dual-instance-info.txt << EOF
AWS Mac Instance Information (Dual Project)
==========================================

Instance ID: $INSTANCE_ID
Instance Type: $INSTANCE_TYPE
Public IP: $PUBLIC_IP
Key Pair: ${KEY_PAIR_NAME}.pem
Security Group: $SECURITY_GROUP_ID
Region: $REGION

SSH Command:
ssh -i ${KEY_PAIR_NAME}.pem ec2-user@$PUBLIC_IP

Service URLs:
- fee_test API: http://$PUBLIC_IP:8000
- DbTest Main: http://$PUBLIC_IP:8001

Service Management:
- Start all: ~/start_all_services.sh
- Stop all: ~/stop_all_services.sh
- Check status: screen -list

Created: $(date)
EOF

success_msg "인스턴스 정보가 'mac-dual-instance-info.txt'에 저장되었습니다"

echo ""
warn_msg "중요 안내사항:"
echo "  - Mac 인스턴스는 최소 24시간 동안 실행되어야 합니다"
echo "  - 24시간 이전에 중지하면 전체 24시간에 대한 요금이 청구됩니다"
echo "  - 두 개의 포트(8000, 8001)가 열려 있습니다"
echo "  - 현재 인스턴스 ID를 기록해 두세요: $INSTANCE_ID"
echo "  - 키 파일을 안전하게 보관하세요: ${KEY_PAIR_NAME}.pem" 