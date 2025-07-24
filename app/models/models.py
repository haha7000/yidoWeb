# app/models/models.py - DECIMAL import 추가된 버전

from sqlalchemy import Column, Integer, String, Text, Boolean, Date, ForeignKey, TIMESTAMP, func, Float, Enum, DECIMAL
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import JSONB
from passlib.context import CryptContext
import enum

Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class DutyFreeType(enum.Enum):
    LOTTE = "lotte"
    SHILLA = "shilla"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(100), nullable=False)
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
    upload_id = Column(String(50), nullable=True) 
    file_path = Column(Text, nullable=True)
    receipt_number = Column(String(50), nullable=True)
    passport_number = Column(String(20), nullable=True)
    commission_total = Column(DECIMAL(12,2), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    user = relationship("User", back_populates="shilla_receipts")

class Passport(Base):
    __tablename__ = "passports"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    upload_id = Column(String(50), nullable=True) 
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
    upload_id = Column(String(50), nullable=True)
    file_path = Column(Text, nullable=True)
    receipt_number = Column(String(50), nullable=True)
    commission_total = Column(DECIMAL(12,2), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    user = relationship("User", back_populates="receipts")

    def __str__(self):
        return f"Receipt(receipt_number={self.receipt_number})"
    
    def __repr__(self):
        return f"Receipt(receipt_number={self.receipt_number})"
    
    
    
class ReceiptMatchLog(Base):
    __tablename__ = "receipt_match_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    upload_id = Column(String(50), nullable=True)
    receipt_number = Column(Text, nullable=True)
    is_matched = Column(Boolean, nullable=False)
    checked_at = Column(TIMESTAMP, server_default=func.now())
    
    # 기존 컬럼들
    excel_name = Column(String(100), nullable=True)
    passport_number = Column(String(20), nullable=True)
    birthday = Column(Date, nullable=True)
    
    # 새로 추가된 매출 상세 정보 컬럼들 (간단하게)
    sales_date = Column(Date, nullable=True) 
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
    commission_rate = Column(DECIMAL(5,4), nullable=True)  # 수수료율 (소수점 4자리까지)
    
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

# === 수수료 관리 모델들 ===

class FeeSettings(Base):
    """수수료 설정 기본 정보"""
    __tablename__ = "fee_settings"
    
    id = Column(Integer, primary_key=True)
    company_name = Column(String(50), nullable=False)  # 면세점명 (LOTTE, SHILLA)
    branch_name = Column(String(100), nullable=False)  # 지점명
    note = Column(Text, nullable=True)  # 메모
    free_rate_threshold = Column(DECIMAL(5,2), nullable=True)  # 수수료 제외 할인율 임계값
    effective_from = Column(Date, nullable=False)  # 시작일
    effective_to = Column(Date, nullable=False)  # 종료일
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True)
    updater_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # 관계 설정
    creator = relationship("User", foreign_keys=[creator_id])
    updater = relationship("User", foreign_keys=[updater_id])
    category_fees = relationship("CategoryFees", back_populates="settings")
    brand_fees = relationship("BrandFees", back_populates="settings")
    item_fees = relationship("ItemFees", back_populates="settings")
    exempt_brands = relationship("ExemptBrands", back_populates="settings")

class CategoryFees(Base):
    """카테고리별 수수료 (7개 고정 구분)"""
    __tablename__ = "category_fees"
    
    id = Column(Integer, primary_key=True)
    settings_id = Column(Integer, ForeignKey("fee_settings.id", ondelete="CASCADE"), nullable=False)
    fee_type = Column(String(20), nullable=False)  # 7개 고정 구분
    commission_rate = Column(DECIMAL(5,4), nullable=False)  # 수수료율
    created_at = Column(TIMESTAMP, server_default=func.now())
    creator_id = Column(Integer, nullable=False)
    
    settings = relationship("FeeSettings", back_populates="category_fees")

class BrandFees(Base):
    """브랜드별 수수료"""
    __tablename__ = "brand_fees"
    
    id = Column(Integer, primary_key=True)
    settings_id = Column(Integer, ForeignKey("fee_settings.id", ondelete="CASCADE"), nullable=False)
    category_code = Column(String(100), nullable=False)
    category_name = Column(String(100), nullable=True)
    import_type = Column(String(50), nullable=False)
    brand_name = Column(String(100), nullable=False)
    commission_rate = Column(DECIMAL(5,4), nullable=False)  # 수수료율
    created_at = Column(TIMESTAMP, server_default=func.now())
    creator_id = Column(Integer, nullable=False)
    
    settings = relationship("FeeSettings", back_populates="brand_fees")

class ItemFees(Base):
    """품목별 수수료"""
    __tablename__ = "item_fees"
    
    id = Column(Integer, primary_key=True)
    settings_id = Column(Integer, ForeignKey("fee_settings.id", ondelete="CASCADE"), nullable=False)
    category_code = Column(String(100), nullable=False)
    category_name = Column(String(100), nullable=True)
    import_type = Column(String(50), nullable=False)
    brand_name = Column(String(100), nullable=False)
    item_name = Column(String(100), nullable=True)
    product_code = Column(String(50), nullable=False)
    commission_rate = Column(DECIMAL(5,4), nullable=False)  # 수수료율
    created_at = Column(TIMESTAMP, server_default=func.now())
    creator_id = Column(Integer, nullable=False)
    
    settings = relationship("FeeSettings", back_populates="item_fees")

class ExemptBrands(Base):
    """수수료 제외 브랜드"""
    __tablename__ = "exempt_brands"
    
    id = Column(Integer, primary_key=True)
    settings_id = Column(Integer, ForeignKey("fee_settings.id", ondelete="CASCADE"), nullable=False)
    category_code = Column(String(100), nullable=False)
    category_name = Column(String(100), nullable=True)
    import_type = Column(String(50), nullable=False)
    brand_name = Column(String(100), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    creator_id = Column(Integer, nullable=False)
    
    settings = relationship("FeeSettings", back_populates="exempt_brands")

class PassportArchive(Base):
    """여권 데이터 아카이브 - 처리 완료된 여권 정보 보관"""
    __tablename__ = "passport_archive"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    upload_id = Column(String(50), nullable=True)
    session_name = Column(String(200), nullable=True)  # 세션명 기록
    original_passport_id = Column(Integer, nullable=True)  # 원본 passport 테이블의 ID
    file_path = Column(Text, nullable=False)
    passport_number = Column(String(20), nullable=True)
    birthday = Column(Date, nullable=True)
    name = Column(String(100), nullable=True)
    is_matched = Column(Boolean, default=False)
    original_created_at = Column(TIMESTAMP, nullable=True)  # 원본 생성일시
    archived_at = Column(TIMESTAMP, server_default=func.now())  # 아카이브 일시

    user = relationship("User")


# class LotteExcelData(Base):
#     """롯데 면세점 엑셀 데이터"""
#     __tablename__ = "lotte_excel_data"
    
#     id = Column(Integer, primary_key=True, autoincrement=True)
    
#     # 기본 정보
#     VIP번호 = Column(Float, nullable=True)  # double precision
#     매출일자 = Column(TIMESTAMP, nullable=True)  # timestamp without time zone
#     단체번호 = Column(Float, nullable=True)  # double precision
#     판매수량 = Column(Integer, nullable=True)  # bigint -> Integer로 매핑
    
#     # 금액 정보 (달러)
#     판매가_달러 = Column(Float, nullable=True, name='판매가($)')  # double precision
#     총매출액_달러 = Column(Integer, nullable=True, name='총매출액($)')  # bigint
#     순매출액_달러 = Column(Integer, nullable=True, name='순매출액($)')  # bigint  
#     할인액_달러 = Column(Integer, nullable=True, name='할인액($)')  # bigint
    
#     # 금액 정보 (원화)
#     총매출액_원 = Column(Integer, nullable=True, name='총매출액(\)')  # bigint
#     순매출액_원 = Column(Integer, nullable=True, name='순매출액(\)')  # bigint
#     할인액_원 = Column(Integer, nullable=True, name='할인액(\)')  # bigint
#     PayBack = Column(Integer, nullable=True)  # bigint
    
#     # 상품 정보
#     상품코드 = Column(Float, nullable=True)  # double precision
#     원매출일자 = Column(TIMESTAMP, nullable=True)  # timestamp without time zone
#     Ref_No = Column(Text, nullable=True, name='Ref.No')  # text
    
#     # 고객 및 영수증 정보
#     name = Column(Text, nullable=True)  # text
#     receiptNumber = Column(Text, nullable=True)  # text
#     교환권상태 = Column(Text, nullable=True)  # text
    
#     # 상품 분류 정보
#     카테고리 = Column(Text, nullable=True)  # text
#     브랜드 = Column(Text, nullable=True)  # text
#     상품명 = Column(Text, nullable=True)  # text
#     상품구분 = Column(Text, nullable=True)  # text
#     점구분 = Column(Text, nullable=True)  # text
#     Color = Column(Text, nullable=True)  # text
#     배송구분 = Column(Text, nullable=True)  # text
#     판매방식 = Column(Text, nullable=True)  # text
    
#     def __repr__(self):
#         return f"<LotteExcelData(name={self.name}, receiptNumber={self.receiptNumber}, 상품명={self.상품명})>"



