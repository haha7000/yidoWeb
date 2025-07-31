#!/usr/bin/env python3
"""
데이터베이스에 기본 사용자 계정 생성 스크립트
"""

import sys
import os

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.models import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_default_user():
    """기본 사용자 계정 생성"""
    db = SessionLocal()
    
    try:
        # 기존 사용자 확인
        existing_user = db.query(User).filter(User.username == "haha").first()
        
        if existing_user:
            print("✅ 사용자 'haha'가 이미 존재합니다.")
            return
        
        # 새 사용자 생성
        hashed_password = pwd_context.hash("haha")
        new_user = User(
            username="haha",
            email="haha@naver.com",
            hashed_password=hashed_password,
            is_active=True
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        print("✅ 사용자 'haha'가 성공적으로 생성되었습니다!")
        print(f"   - 사용자명: haha")
        print(f"   - 이메일: haha@example.com")
        print(f"   - 비밀번호: haha")
        
    except Exception as e:
        print(f"❌ 사용자 생성 중 오류 발생: {e}")
        db.rollback()
    finally:
        db.close()

def list_users():
    """현재 등록된 사용자 목록 출력"""
    db = SessionLocal()
    
    try:
        users = db.query(User).all()
        
        if not users:
            print("📋 등록된 사용자가 없습니다.")
            return
        
        print("📋 현재 등록된 사용자 목록:")
        for user in users:
            print(f"   - ID: {user.id}, 사용자명: {user.username}, 이메일: {user.email}, 활성화: {user.is_active}")
            
    except Exception as e:
        print(f"❌ 사용자 목록 조회 중 오류 발생: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 사용자 계정 관리 스크립트")
    print("=" * 50)
    
    # 사용자 목록 출력
    list_users()
    print()
    
    # 기본 사용자 생성
    create_default_user()
    print()
    
    # 생성 후 사용자 목록 다시 출력
    list_users() 
