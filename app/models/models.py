from sqlalchemy import Column, Integer, String, Text, Boolean, Date, ForeignKey, TIMESTAMP, func, Float
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class Passport(Base):
    __tablename__ = "passports"

    id = Column(Integer, primary_key=True)
    file_path = Column(Text, nullable=False)
    passport_number = Column(String(20), nullable=True)
    birthday = Column(Date, nullable=True)
    name = Column(String(100), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    is_matched = Column(Boolean, default=False)

class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True)
    file_path = Column(Text, nullable=True)
    receipt_number = Column(String(50), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    def __str__(self):
        return f"Receipt(receipt_number={self.receipt_number})"
    
    def __repr__(self):
        return f"Receipt(receipt_number={self.receipt_number})"
    
class ReceiptMatchLog(Base):
    __tablename__ = "receipt_match_log"

    id = Column(Integer, primary_key=True)
    receipt_number = Column(Text, nullable=True)
    is_matched = Column(Boolean, nullable=False)
    checked_at = Column(TIMESTAMP, server_default=func.now())
    excel_name = Column(String(100), nullable=True)
    passport_number = Column(String(20), nullable=True)
    birthday = Column(Date, nullable=True)

class UnrecognizedImage(Base):
    __tablename__ = "unrecognized_images"

    id = Column(Integer, primary_key=True)
    file_path = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    def __str__(self):
        return f"UnrecognizedImage(file_path={self.file_path})"
    
    def __repr__(self):
        return f"UnrecognizedImage(file_path={self.file_path})"