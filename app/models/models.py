# app/models/models.py - DECIMAL import 추가된 버전

from sqlalchemy import Column, Integer, String, Text, Boolean, Date, ForeignKey, TIMESTAMP, func, Float, Enum, DECIMAL
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import JSONB
from passlib.context import CryptContext
import enum

Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# DutyFreeType enum은 유지하되, User 모델에서는 제거
class DutyFreeType(enum.Enum):
    LOTTE = "lotte"
    SHILLA = "shilla"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(100), nullable=False)
    # duty_free_type 필드 제거됨
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # 관계 설정
    receipts = relationship("Receipt", back_populates="user")
    passports = relationship("Passport", back_populates="user")
    shilla_receipts = relationship("ShillaReceipt", back_populates="user")
    archives = relationship("ProcessingArchive", back_populates="user")
    processing_histories = relationship("ProcessingHistory", back_populates="user")
    
    def verify_password(self, password: str) -> bool:
        return pwd_context.verify(password, self.hashed_password)
    
    @classmethod
    def hash_password(cls, password: str) -> str:
        return pwd_context.hash(password)

# 신라 영수증 모델 
class ShillaReceipt(Base):
    __tablename__ = "shilla_receipts"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    upload_id = Column(String(50), nullable=True)  # 업로드 ID 추가
    file_path = Column(Text, nullable=True)
    receipt_number = Column(String(50), nullable=True)
    passport_number = Column(String(20), nullable=True)
    commission_total = Column(DECIMAL(12,2), nullable=True)  # 수수료 합계
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    user = relationship("User", back_populates="shilla_receipts")

class Passport(Base):
    __tablename__ = "passports"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    upload_id = Column(String(50), nullable=True)  # 업로드 ID 추가
    file_path = Column(Text, nullable=False)
    passport_number = Column(String(20), nullable=True)
    birthday = Column(Date, nullable=True)
    name = Column(String(100), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    is_matched = Column(Boolean, default=False)

    user = relationship("User", back_populates="passports")

class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    upload_id = Column(String(50), nullable=True)  # 업로드 ID 추가
    file_path = Column(Text, nullable=True)
    receipt_number = Column(String(50), nullable=True)
    commission_total = Column(DECIMAL(12,2), nullable=True)  # 수수료 합계
    created_at = Column(TIMESTAMP, server_default=func.now())

    def __str__(self):
        return f"Receipt(receipt_number={self.receipt_number})"
    
    def __repr__(self):
        return f"Receipt(receipt_number={self.receipt_number})"
    
    user = relationship("User", back_populates="receipts")
    
class ReceiptMatchLog(Base):
    __tablename__ = "receipt_match_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    upload_id = Column(String(50), nullable=True)  # 업로드 ID 추가
    receipt_number = Column(Text, nullable=True)
    is_matched = Column(Boolean, nullable=False)
    checked_at = Column(TIMESTAMP, server_default=func.now())
    
    # 기존 컬럼들
    excel_name = Column(String(100), nullable=True)
    passport_number = Column(String(20), nullable=True)
    birthday = Column(Date, nullable=True)
    
    # 새로 추가된 매출 상세 정보 컬럼들 (간단하게)
    sales_date = Column(Date, nullable=True)  # 매출일자
    category = Column(String(100), nullable=True)  # 카테고리
    brand = Column(String(100), nullable=True)  # 브랜드
    product_code = Column(String(50), nullable=True)  # 상품코드
    discount_amount_krw = Column(Float, nullable=True)  # 할인액(원)
    sales_price_usd = Column(Float, nullable=True)  # 판매가(달러)
    net_sales_krw = Column(Float, nullable=True)  # 순매출액(원)
    store_branch = Column(String(100), nullable=True)  # 점포구분 (롯데: 점구분, 신라: 점)
    
    # 할인율 및 수수료 계산 컬럼들
    discount_rate = Column(DECIMAL(5,2), nullable=True)  # 할인율 (%)
    commission_fee = Column(DECIMAL(12,2), nullable=True)  # 계산된 수수료 (원)
    
    # 면세점 타입 (lotte, shilla)
    duty_free_type = Column(String(20), nullable=True)  # 면세점 타입

class UnrecognizedImage(Base):
    __tablename__ = "unrecognized_images"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    upload_id = Column(String(50), nullable=True)  # 업로드 ID 추가
    file_path = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    def __str__(self):
        return f"UnrecognizedImage(file_path={self.file_path})"
    
    def __repr__(self):
        return f"UnrecognizedImage(file_path={self.file_path})"

# === 새로 추가된 아카이브 관련 모델들 ===

class ProcessingArchive(Base):
    """처리 완료된 세션 아카이브"""
    __tablename__ = "processing_archives"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_name = Column(String(200), nullable=False)
    archive_date = Column(TIMESTAMP, server_default=func.now())
    
    # 통계 정보
    total_receipts = Column(Integer, default=0)
    matched_receipts = Column(Integer, default=0)
    total_passports = Column(Integer, default=0)
    matched_passports = Column(Integer, default=0)
    
    # 메타데이터
    duty_free_type = Column(String(20), nullable=True)
    notes = Column(Text, nullable=True)
    
    # 상세 데이터 (JSON)
    archive_data = Column(JSONB, nullable=True)
    
    user = relationship("User", back_populates="archives")
    matching_histories = relationship("MatchingHistory", back_populates="archive")

class MatchingHistory(Base):
    """매칭 이력 저장"""
    __tablename__ = "matching_history"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    archive_id = Column(Integer, ForeignKey("processing_archives.id"), nullable=True)
    
    # 매칭 정보
    customer_name = Column(String(100), nullable=True)
    passport_number = Column(String(20), nullable=True)
    receipt_numbers = Column(Text, nullable=True)  # JSON 문자열로 저장
    excel_data = Column(JSONB, nullable=True)
    
    # 매칭 상태
    match_status = Column(String(50), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    user = relationship("User")
    archive = relationship("ProcessingArchive", back_populates="matching_histories")

# === 처리 완료된 데이터 저장용 테이블 ===

class ProcessingHistory(Base):
    """처리 완료된 매칭 데이터 이력"""
    __tablename__ = "processing_history"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    upload_id = Column(String(50), nullable=False)  # 업로드 세션 ID
    session_name = Column(String(200), nullable=False)  # 사용자가 지정한 세션명
    
    # 원본 ReceiptMatchLog 데이터 복사
    receipt_number = Column(Text, nullable=True)
    is_matched = Column(Boolean, nullable=False)
    excel_name = Column(String(100), nullable=True)
    passport_number = Column(String(20), nullable=True)
    birthday = Column(Date, nullable=True)
    
    # 매출 상세 정보
    sales_date = Column(Date, nullable=True)
    category = Column(String(100), nullable=True)
    brand = Column(String(100), nullable=True)
    product_code = Column(String(50), nullable=True)
    discount_amount_krw = Column(Float, nullable=True)
    sales_price_usd = Column(Float, nullable=True)
    net_sales_krw = Column(Float, nullable=True)
    store_branch = Column(String(100), nullable=True)
    
    # 할인율 및 수수료 계산
    discount_rate = Column(DECIMAL(5,2), nullable=True)
    commission_fee = Column(DECIMAL(12,2), nullable=True)
    
    # 면세점 타입
    duty_free_type = Column(String(20), nullable=True)
    
    # 타임스탬프
    processed_at = Column(TIMESTAMP, nullable=False)  # 원본 처리 시각
    archived_at = Column(TIMESTAMP, server_default=func.now())  # 아카이브 시각
    
    user = relationship("User", back_populates="processing_histories")