from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# 환경변수에서 데이터베이스 정보 가져오기
user = os.getenv('DB_USER', 'test_user')
password = os.getenv('DB_PASSWORD', '0000')
host = os.getenv('DB_HOST', 'localhost')
port = os.getenv('DB_PORT', '5432')
database = os.getenv('DB_NAME', 'my_test_db')

SQLALCHEMY_DATABASE_URL = f'postgresql://{user}:{password}@{host}:{port}/{database}'
my_engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=my_engine)

def get_db():
    """
    FastAPI 의존성 주입용 데이터베이스 세션 생성 함수
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()