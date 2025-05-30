from sqlalchemy import Column, Integer, String, Text, Boolean, Date, ForeignKey, TIMESTAMP, func, Float, Enum
from sqlalchemy.orm import relationship, declarative_base
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
    duty_free_type = Column(Enum(DutyFreeType), nullable=False, default=DutyFreeType.LOTTE)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # 관계 설정
    receipts = relationship("Receipt", back_populates="user")
    passports = relationship("Passport", back_populates="user")
    shilla_receipts = relationship("ShillaReceipt", back_populates="user")
    
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
    file_path = Column(Text, nullable=True)
    receipt_number = Column(String(50), nullable=True)
    passport_number = Column(String(20), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    user = relationship("User", back_populates="shilla_receipts")

# 엑셀 데이터 모델들은 제거하고 동적으로 테이블 생성
# LotteExcelData와 ShillaExcelData 클래스 제거

class Passport(Base):
    __tablename__ = "passports"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
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
    file_path = Column(Text, nullable=True)
    receipt_number = Column(String(50), nullable=True)
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
    receipt_number = Column(Text, nullable=True)
    is_matched = Column(Boolean, nullable=False)
    checked_at = Column(TIMESTAMP, server_default=func.now())
    excel_name = Column(String(100), nullable=True)
    passport_number = Column(String(20), nullable=True)
    birthday = Column(Date, nullable=True)

class UnrecognizedImage(Base):
    __tablename__ = "unrecognized_images"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_path = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    def __str__(self):
        return f"UnrecognizedImage(file_path={self.file_path})"
    
    def __repr__(self):
        return f"UnrecognizedImage(file_path={self.file_path})"