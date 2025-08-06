#!/usr/bin/env python3
"""
SMTP 연결 테스트 스크립트
"""
import smtplib
import os
from dotenv import load_dotenv

load_dotenv()

def test_smtp_connection():
    username = os.getenv('SMTP_USERNAME', 'ghehdch13@gmail.com')
    password = os.getenv('SMTP_PASSWORD', 'ibhznjbtdprghrvt')
    
    print(f"🔍 SMTP 연결 테스트")
    print(f"📧 계정: {username}")
    print(f"🔑 비밀번호: {password[:4]}****{password[-4:]}")
    print("-" * 50)
    
    try:
        print("1️⃣ SMTP 서버 연결 중...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        
        print("2️⃣ TLS 시작...")
        server.starttls()
        
        print("3️⃣ 로그인 시도...")
        server.login(username, password)
        
        print("✅ SMTP 연결 성공!")
        server.quit()
        return True
        
    except Exception as e:
        print(f"❌ SMTP 연결 실패: {str(e)}")
        return False

if __name__ == "__main__":
    test_smtp_connection()