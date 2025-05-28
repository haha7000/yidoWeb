# create_tables.py
from app.core.database import my_engine
from app.models.models import Base

Base.metadata.drop_all(bind=my_engine)     # 테이블 모두 삭제
Base.metadata.create_all(bind=my_engine)   # 테이블 새로 생성
print("📦 테이블 초기화 및 재생성 완료!")
