from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

user = 'test_user'
password = '0000'
host = 'localhost'
port = '5432'
database = 'my_test_db'

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