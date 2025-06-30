import requests
import re
import hashlib
import base64
from urllib.parse import urlencode

def encrypt_password_correct(password: str) -> str:
    """브라우저와 동일한 방식으로 암호화"""
    step1_input = "" + password  # 빈 salt
    step1_hash = hashlib.sha512(step1_input.encode()).digest()
    result = base64.b64encode(step1_hash).decode()
    return result

# 세션 생성
session = requests.Session()

# 더 상세한 헤더 설정
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Cache-Control': 'max-age=0'
})

print("[INFO] 로그인 페이지 접근...")
login_page_url = "https://www.shillasrm.com/login.do"
res = session.get(login_page_url)
html = res.text

# CSRF 토큰 추출
csrf_token = re.search(r'name="_csrf"\s+value="([^"]+)"', html)
csrf_token = csrf_token.group(1) if csrf_token else None
print(f"[+] CSRF Token: {csrf_token}")

# 폼의 모든 hidden 필드 추출
hidden_fields = re.findall(r'<input[^>]*type=["\']hidden["\'][^>]*>', html, re.IGNORECASE)
print(f"\n[INFO] Hidden 필드들:")
for field in hidden_fields:
    print(f"  {field}")

# 다른 CSRF 관련 필드들 찾기
csrf_header = re.search(r'name="_csrf_header"\s+content="([^"]+)"', html)
csrf_param = re.search(r'name="_csrf_parameter"\s+content="([^"]+)"', html)

if csrf_header:
    print(f"[+] CSRF Header: {csrf_header.group(1)}")
if csrf_param:
    print(f"[+] CSRF Parameter: {csrf_param.group(1)}")

# 비밀번호 암호화
plain_pw = "19850327ng@!!"
encrypted_pw = encrypt_password_correct(plain_pw)
print(f"[+] 암호화된 비밀번호: {encrypted_pw}")

# 로그인 시도 1: 기본 방식
print("\n" + "="*60)
print("로그인 시도 1: 기본 방식")
print("="*60)

login_url = "https://www.shillasrm.com/loginProcess.do"
payload = {
    "username": "G000056324",
    "password": encrypted_pw,
    "pro_cls": "2",
    "company": "",
    "type": "",
    "lang": "",
    "_csrf": csrf_token
}

headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": login_page_url,
    "Origin": "https://www.shillasrm.com"
}

login_res = session.post(login_url, data=payload, headers=headers, allow_redirects=False)
print(f"[+] Status: {login_res.status_code}")
print(f"[+] Location: {login_res.headers.get('Location', 'N/A')}")

# 로그인 실패 페이지 확인
if 'loginFailure' in login_res.headers.get('Location', ''):
    print("\n[INFO] 로그인 실패 페이지 확인...")
    failure_res = session.get(login_res.headers['Location'])
    failure_html = failure_res.text
    
    # 에러 메시지 추출 시도
    error_patterns = [
        r'<div[^>]*class[^>]*error[^>]*>([^<]+)</div>',
        r'<span[^>]*class[^>]*error[^>]*>([^<]+)</span>',
        r'<p[^>]*class[^>]*error[^>]*>([^<]+)</p>',
        r'alert\(["\']([^"\']+)["\']',
        r'오류|에러|실패|잘못',
    ]
    
    for pattern in error_patterns:
        matches = re.findall(pattern, failure_html, re.IGNORECASE)
        if matches:
            print(f"[ERROR] 발견된 오류 메시지: {matches}")
    
    print(f"\n[DEBUG] 실패 페이지 일부 (처음 1000자):")
    print(failure_html[:1000])

# 로그인 시도 2: 다른 필드값 조합 테스트
print("\n" + "="*60)
print("로그인 시도 2: 다른 필드값 조합")
print("="*60)

test_combinations = [
    # pro_cls 값 변경
    {"username": "G000056324", "password": encrypted_pw, "pro_cls": "1", "_csrf": csrf_token},
    {"username": "G000056324", "password": encrypted_pw, "pro_cls": "", "_csrf": csrf_token},
    # company 값 변경
    {"username": "G000056324", "password": encrypted_pw, "pro_cls": "2", "company": "SHILLA", "_csrf": csrf_token},
    # 최소한의 필드만
    {"username": "G000056324", "password": encrypted_pw, "_csrf": csrf_token},
]

for i, test_payload in enumerate(test_combinations, 1):
    print(f"\n[TEST {i}] 페이로드: {test_payload}")
    test_res = session.post(login_url, data=test_payload, headers=headers, allow_redirects=False)
    location = test_res.headers.get('Location', 'N/A')
    print(f"[TEST {i}] Status: {test_res.status_code}, Location: {location}")
    
    if location != 'N/A' and 'loginFailure' not in location:
        print(f"✅ [TEST {i}] 성공 가능성 있음!")
        break

# 로그인 시도 3: 암호화하지 않은 비밀번호로 테스트
print("\n" + "="*60)
print("로그인 시도 3: 암호화하지 않은 비밀번호")
print("="*60)

payload_plain = {
    "username": "G000056324",
    "password": plain_pw,  # 암호화하지 않은 원본
    "pro_cls": "2",
    "company": "",
    "type": "",
    "lang": "",
    "_csrf": csrf_token
}

plain_res = session.post(login_url, data=payload_plain, headers=headers, allow_redirects=False)
print(f"[+] Status: {plain_res.status_code}")
print(f"[+] Location: {plain_res.headers.get('Location', 'N/A')}")

# 최종 상태 확인
print("\n" + "="*60)
print("최종 세션 상태 확인")
print("="*60)

print("[INFO] 현재 쿠키:")
for cookie in session.cookies:
    print(f"  - {cookie.name}: {cookie.value}")

# 다른 엔드포인트들 테스트
test_endpoints = [
    "https://www.shillasrm.com/",
    "https://www.shillasrm.com/main.do",
    "https://www.shillasrm.com/index.do"
]

for endpoint in test_endpoints:
    try:
        test_res = session.get(endpoint, allow_redirects=False)
        print(f"[+] {endpoint} -> Status: {test_res.status_code}, Location: {test_res.headers.get('Location', 'Direct')}")
    except Exception as e:
        print(f"[+] {endpoint} -> Error: {e}")