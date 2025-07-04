# 🍎 AWS Mac 인스턴스 승인 요청 가이드

## 승인이 필요한 이유
AWS Mac 인스턴스는 Apple의 라이선스 제약으로 인해 **사전 승인**이 필요합니다.

## 승인 요청 방법

### 1. AWS Support 센터 접속
- AWS 콘솔에서 **Support** → **Support Center** 이동
- 또는 직접 링크: https://console.aws.amazon.com/support/home

### 2. 새 케이스 생성
1. **Create case** 클릭
2. **Service limit increase** 선택
3. **Case details** 입력:
   - **Service**: EC2 Instances
   - **Category**: Instance Type
   - **Severity**: General guidance
   - **Use case description**: 
     ```
     I would like to request access to AWS Mac instances (mac1.metal and mac2.metal) 
     for mobile application development and testing purposes.
     
     Business justification:
     - Need to run macOS-based development environment
     - Require Mac instances for iOS app development
     - Temporary development and testing workloads
     
     Estimated usage:
     - Instance type: mac2.metal
     - Expected duration: 2-4 weeks
     - Region: us-east-1
     ```

### 3. 필요한 정보
- **AWS Account ID**: 042829937449
- **사용 목적**: iOS 개발, 테스트 환경
- **예상 사용 기간**: 2-4주
- **지역**: us-east-1

### 4. 승인 처리 시간
- 일반적으로 **24-48시간** 소요
- 영업일 기준으로 처리

## 🔄 대안 1: 일반 EC2 인스턴스 사용

Mac 인스턴스 승인을 기다리는 동안 **Ubuntu EC2 인스턴스**로 배포할 수 있습니다:

```bash
# 일반 EC2 인스턴스로 배포
./create-ec2-instance.sh  # 새로 만들 예정
```

## 🔄 대안 2: 로컬 macOS 개발

현재 macOS 환경에서 개발을 계속하면서 필요 시 Linux 서버로 배포

## 승인 후 절차

승인이 완료되면:
1. **이메일 알림** 수신
2. 기존 스크립트 실행:
   ```bash
   ./create-mac-instance-dual.sh
   ```
3. 정상적으로 Mac 인스턴스 생성 가능

## 참고 사항

- **비용**: Mac 인스턴스는 **최소 24시간** 과금 (중간에 중지해도 24시간 요금 부과)
- **인스턴스 타입**: mac2.metal (M2), mac1.metal (Intel)
- **지원 지역**: us-east-1, us-west-2, eu-west-1, ap-southeast-2

## 문의사항

승인 관련 문의는 AWS Support를 통해 진행하세요. 