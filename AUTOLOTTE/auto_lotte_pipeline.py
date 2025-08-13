#!/usr/bin/env python3
"""
롯데 면세점 자동화 파이프라인
1. 엑셀 데이터 다운로드 (데이터 타입 변환 포함)
2. DB 자동 업로드
"""

import os
import sys
import logging
import time
from datetime import datetime
from typing import Optional, Tuple, Dict
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 로컬 모듈 import
from lotte_scraper import LotteDutyFreeSales
from app.models.models import LotteExcelData, Base

# execl_test.py import는 더 이상 필요없음 (exporter.py에서 데이터 타입 변환 처리)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lotte_pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LotteAutoPipeline:
    """롯데 면세점 자동화 파이프라인"""

    def __init__(self, db_url: str = "postgresql://test_user:test_password@localhost:5432/my_test_db"):
        """
        파이프라인 초기화

        Args:
            db_url (str): PostgreSQL 연결 URL
        """
        self.db_url = db_url
        self.engine = None
        self.Session = None
        self.scraper = LotteDutyFreeSales()
        self.downloaded_file = None

        # DB 연결 설정
        self._setup_database()

        # 작업 디렉토리 설정
        self.work_dir = os.path.join(os.path.dirname(__file__), 'downloads')
        os.makedirs(self.work_dir, exist_ok=True)

    def _setup_database(self):
        """데이터베이스 연결 설정"""
        try:
            self.engine = create_engine(self.db_url)
            self.Session = sessionmaker(bind=self.engine)

           # 테이블 생성 확인
            Base.metadata.create_all(self.engine)
            logger.info("✅ 데이터베이스 연결 및 테이블 생성 완료")

        except Exception as e:
            logger.error(f"❌ 데이터베이스 연결 실패: {e}")
            raise

    def step1_download_excel(self, user_id: str = 'T301912', password: str = 'huixin210@') -> bool:
        """
        1단계: 엑셀 데이터 다운로드

        Args:
            user_id (str): 로그인 ID
            password (str): 로그인 비밀번호

        Returns:
            bool: 다운로드 성공 여부
        """
        logger.info("🚀 1단계: 엑셀 데이터 다운로드 시작")

        try:
            # 로그인 (세션 갱신)
            logger.info("🔐 로그인 중...")
            if not self.scraper.login(user_id, password):
                logger.error("❌ 로그인 실패")
                return False

            # 세션 유효성 확인 및 재로그인
            max_retries = 3
            for attempt in range(max_retries):
                logger.info(f"📊 매출 데이터 조회 시도 {attempt + 1}/{max_retries}...")

                # 세션 유효성 사전 확인
                if not self.scraper.auth.validate_session():
                    logger.warning("⚠️ 세션 유효성 검증 실패, 재로그인 시도...")
                    if not self.scraper.login(user_id, password):
                        logger.error("❌ 재로그인 실패")
                        return False
                    time.sleep(2)  # 잠시 대기

                # 매출 데이터 조회 (자동 세션 갱신 포함)
                sales_data = self.scraper.fetch_product_sales()

                if not sales_data:
                    logger.warning("⚠️ 상품별 조회 실패, 브랜드별 조회로 폴백...")
                    sales_data = self.scraper.fetch_brand_sales()

                if sales_data:
                    logger.info(f"✅ 매출 데이터 조회 성공: {len(sales_data)}건")
                    break
                else:
                    logger.warning(f"⚠️ 시도 {attempt + 1} 실패")
                    if attempt < max_retries - 1:  # 마지막 시도가 아니면 재로그인
                        logger.info("🔄 세션 재로그인 시도...")
                        if not self.scraper.login(user_id, password):
                            logger.error("❌ 재로그인 실패")
                            return False
                        time.sleep(3)  # 재로그인 후 더 긴 대기

            if not sales_data:
                logger.error("❌ 모든 매출 데이터 조회 실패")
                return False

            # 엑셀 파일 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"lotte_sales_{timestamp}.xlsx"

            logger.info(f"💾 엑셀 파일 저장 중: {filename}")

            # 엑셀 저장 (exporter가 다운로드 폴더에 저장)
            if self.scraper.save_to_excel(filename=filename):
                # 저장된 파일 경로를 찾기 위해 다운로드 폴더 확인
                downloads_folder = self.scraper.exporter.get_downloads_folder()
                file_path = downloads_folder / filename
                self.downloaded_file = str(file_path)
                logger.info(f"✅ 엑셀 다운로드 완료: {self.downloaded_file}")
                return True
            else:
                logger.error("❌ 엑셀 저장 실패")
                return False

        except Exception as e:
            logger.error(f"❌ 다운로드 중 오류 발생: {e}")
            return False

    def step2_upload_to_db(self, batch_size: int = 1000) -> bool:
        """
        2단계: DB 자동 업로드

        Args:
            batch_size (int): 배치 크기

        Returns:
            bool: 업로드 성공 여부
        """
        logger.info("🗄️  2단계: DB 자동 업로드 시작")

        if not self.downloaded_file or not os.path.exists(self.downloaded_file):
            logger.error("❌ 다운로드된 파일이 없습니다")
            return False

        try:
            # 엑셀 파일 읽기 (exporter.py에서 이미 데이터 타입 변환됨)
            logger.info(f"📖 엑셀 파일 읽기 중: {self.downloaded_file}")
            df = pd.read_excel(self.downloaded_file)

            session = self.Session()

            # 기존 데이터 확인 (선택사항)
            existing_count = session.query(LotteExcelData).count()
            logger.info(f"📊 기존 데이터 수: {existing_count:,}건")

            # 배치 단위로 데이터 삽입
            total_rows = len(df)
            inserted_count = 0

            logger.info(f"📥 총 {total_rows:,}건의 데이터를 배치 크기 {batch_size}로 업로드 중...")

            for i in range(0, total_rows, batch_size):
                batch_df = df.iloc[i:i+batch_size]

                # 배치 데이터를 DB 모델로 변환
                batch_records = []
                for _, row in batch_df.iterrows():
                    record = LotteExcelData()

                    # 컬럼별로 데이터 할당
                    for col in df.columns:
                        if hasattr(record, col):
                            setattr(record, col, row[col])

                    batch_records.append(record)

                # 배치 삽입
                session.add_all(batch_records)
                session.commit()

                inserted_count += len(batch_records)
                logger.info(f"📦 배치 완료: {inserted_count:,}/{total_rows:,}건")

            session.close()

            logger.info(f"✅ DB 업로드 완료: {inserted_count:,}건 삽입됨")
            return True

        except Exception as e:
            logger.error(f"❌ DB 업로드 중 오류 발생: {e}")
            if session:
                session.rollback()
                session.close()
            return False

    def run_full_pipeline(self, user_id: str = 'T301912', password: str = 'huixin210@') -> bool:
        """
        전체 파이프라인 실행

        Args:
            user_id (str): 로그인 ID
            password (str): 로그인 비밀번호

        Returns:
            bool: 전체 프로세스 성공 여부
        """
        logger.info("🚀 롯데 면세점 자동화 파이프라인 시작")
        logger.info("=" * 60)

        start_time = datetime.now()

        try:
            # 1단계: 엑셀 다운로드 (데이터 타입 변환 포함)
            if not self.step1_download_excel(user_id, password):
                logger.error("❌ 1단계 실패로 파이프라인 중단")
                return False

            # 2단계: DB 업로드
            if not self.step2_upload_to_db():
                logger.error("❌ 2단계 실패로 파이프라인 중단")
                return False

            end_time = datetime.now()
            duration = end_time - start_time

            # 처리된 데이터 건수 확인
            try:
                df = pd.read_excel(self.downloaded_file)
                data_count = len(df)
            except:
                data_count = "알 수 없음"

            logger.info("=" * 60)
            logger.info(f"🎉 전체 파이프라인 완료!")
            logger.info(f"⏱️  소요 시간: {duration}")
            logger.info(f"📁 다운로드 파일: {self.downloaded_file}")
            logger.info(f"📊 처리된 데이터: {data_count}건")

            return True

        except Exception as e:
            logger.error(f"❌ 파이프라인 실행 중 오류 발생: {e}")
            return False

    def cleanup(self):
        """정리 작업"""
        try:
            # 다운로드된 파일 정리 (선택사항)
            if self.downloaded_file and os.path.exists(self.downloaded_file):
                os.remove(self.downloaded_file)  # 주석 해제하면 파일 삭제
                logger.info(f"🧹 임시 파일 정리: {self.downloaded_file}")
        except Exception as e:
            logger.warning(f"⚠️ 정리 작업 중 오류: {e}")

def main():
    """메인 실행 함수"""
    # 환경 변수에서 설정 가져오기 (선택사항)
    db_url = os.getenv('LOTTE_DB_URL', "postgresql://test_user:test_password@localhost:5432/my_test_db")
    user_id = os.getenv('LOTTE_USER_ID', 'T301912')
    password = os.getenv('LOTTE_PASSWORD', 'huixin210@')

    # 파이프라인 실행
    pipeline = LotteAutoPipeline(db_url)

    try:
        success = pipeline.run_full_pipeline(user_id, password)

        if success:
            print("\n🎉 파이프라인 성공적으로 완료되었습니다!")
        else:
            print("\n❌ 파이프라인 실행 중 오류가 발생했습니다.")
            sys.exit(1)

    finally:
        # 정리 작업
        pipeline.cleanup()

if __name__ == "__main__":
    main()