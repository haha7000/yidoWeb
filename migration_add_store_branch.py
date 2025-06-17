"""
receipt_match_log 테이블에 store_branch 컬럼 추가 마이그레이션
"""

from sqlalchemy import create_engine, text
from app.core.database import DATABASE_URL
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_store_branch_column():
    """receipt_match_log 테이블에 store_branch 컬럼 추가"""
    
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as connection:
            # 트랜잭션 시작
            trans = connection.begin()
            
            try:
                # store_branch 컬럼이 이미 존재하는지 확인
                check_column_sql = """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'receipt_match_log' 
                AND column_name = 'store_branch'
                """
                
                result = connection.execute(text(check_column_sql)).fetchone()
                
                if result:
                    logger.info("store_branch 컬럼이 이미 존재합니다.")
                    trans.rollback()
                    return
                
                # store_branch 컬럼 추가
                add_column_sql = """
                ALTER TABLE receipt_match_log 
                ADD COLUMN store_branch VARCHAR(100)
                """
                
                connection.execute(text(add_column_sql))
                logger.info("store_branch 컬럼이 성공적으로 추가되었습니다.")
                
                # 변경사항 커밋
                trans.commit()
                logger.info("마이그레이션이 완료되었습니다.")
                
            except Exception as e:
                trans.rollback()
                logger.error(f"마이그레이션 중 오류 발생: {e}")
                raise
                
    except Exception as e:
        logger.error(f"데이터베이스 연결 오류: {e}")
        raise

if __name__ == "__main__":
    logger.info("receipt_match_log 테이블에 store_branch 컬럼 추가 마이그레이션 시작")
    add_store_branch_column()
    logger.info("마이그레이션 완료") 