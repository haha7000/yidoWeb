"""
사용자별 자동화 서비스
각 사용자의 면세점 계정으로 개별 자동화 실행
"""
import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.models.models import User, DutyFreeAccount, AutomationLog, LotteExcelData, ShillaExcelData
from app.core.database import SessionLocal

# AUTOLOTTE 및 AUTOSHILLA 모듈 import
try:
    # AUTOLOTTE 경로를 절대 경로로 추가
    autolotte_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'AUTOLOTTE')
    if autolotte_path not in sys.path:
        sys.path.append(autolotte_path)
    
    from lotte_scraper import LotteDutyFreeSales
    from auth import LotteAuth
    from exporter import LotteExporter
except ImportError as e:
    logging.warning(f"AUTOLOTTE 모듈 import 실패: {e}")
    LotteDutyFreeSales = None
    LotteAuth = None
    LotteExporter = None

try:
    # AUTOSHILLA 경로를 절대 경로로 추가
    autoshilla_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'AUTOSHILLA')
    if autoshilla_path not in sys.path:
        sys.path.append(autoshilla_path)
    
    from shilla_rpa import main as shilla_main
    from excel_processor import ExcelProcessor
except ImportError as e:
    logging.warning(f"AUTOSHILLA 모듈 import 실패: {e}")
    shilla_main = None
    ExcelProcessor = None

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UserAutomationService:
    """사용자별 자동화 서비스"""
    
    def __init__(self):
        self.db_session = None
    
    def get_db_session(self) -> Session:
        """데이터베이스 세션 획득"""
        if not self.db_session:
            self.db_session = SessionLocal()
        return self.db_session
    
    def close_db_session(self):
        """데이터베이스 세션 종료"""
        if self.db_session:
            self.db_session.close()
            self.db_session = None
    
    def get_active_accounts(self) -> List[DutyFreeAccount]:
        """활성화된 면세점 계정 목록 조회"""
        db = self.get_db_session()
        try:
            accounts = db.query(DutyFreeAccount).filter(
                DutyFreeAccount.is_active == True
            ).all()
            
            logger.info(f"활성화된 계정 {len(accounts)}개 발견")
            return accounts
        except Exception as e:
            logger.error(f"활성화된 계정 조회 오류: {e}")
            return []
    
    def create_automation_log(self, account: DutyFreeAccount, status: str = "running", message: str = None) -> AutomationLog:
        """자동화 로그 생성"""
        db = self.get_db_session()
        try:
            log = AutomationLog(
                account_id=account.id,
                duty_free_type=account.duty_free_type,
                status=status,
                message=message,
                started_at=datetime.now()
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            
            logger.info(f"자동화 로그 생성: {account.duty_free_type} - {account.username}")
            return log
        except Exception as e:
            logger.error(f"자동화 로그 생성 오류: {e}")
            db.rollback()
            raise e
    
    def update_automation_log(self, log: AutomationLog, status: str, message: str = None, records_count: int = None):
        """자동화 로그 업데이트"""
        db = self.get_db_session()
        try:
            log.status = status
            log.message = message
            log.records_count = records_count
            log.completed_at = datetime.now()
            
            db.commit()
            logger.info(f"자동화 로그 업데이트: {status} - {message}")
        except Exception as e:
            logger.error(f"자동화 로그 업데이트 오류: {e}")
            db.rollback()
            raise e
    
    async def run_lotte_automation(self, account: DutyFreeAccount) -> Dict:
        """롯데 면세점 자동화 실행"""
        log = self.create_automation_log(account, "running", "롯데 자동화 시작")
        
        try:
            logger.info(f"롯데 자동화 시작: {account.username}")
            
            if not LotteDutyFreeSales or not LotteAuth or not LotteExporter:
                raise ImportError("롯데 자동화 모듈이 없습니다")
            
            # 롯데 스크레이퍼 초기화
            scraper = LotteDutyFreeSales()
            
            # 로그인
            login_success = scraper.login(account.username, account.password)
            if not login_success:
                self.update_automation_log(log, "failed", "로그인 실패")
                return {"success": False, "message": "로그인 실패"}
            
            # 데이터 수집 (상품별 매출 데이터)
            sales_data = scraper.fetch_product_sales()
            if not sales_data:
                # 상품별 실패 시 브랜드별로 시도
                sales_data = scraper.fetch_brand_sales()
                
            if not sales_data:
                self.update_automation_log(log, "failed", "데이터 수집 실패: 매출 데이터를 가져올 수 없습니다")
                return {"success": False, "message": "매출 데이터를 가져올 수 없습니다"}
            
            # 엑셀 데이터 변환 및 DB 저장
            records_count = await self.save_lotte_data_to_db(sales_data, account.user_id)
            
            self.update_automation_log(log, "success", f"데이터 수집 및 저장 완료", records_count)
            
            logger.info(f"롯데 자동화 완료: {account.username} - {records_count}건")
            return {"success": True, "message": f"{records_count}건 처리 완료", "records_count": records_count}
            
        except Exception as e:
            error_msg = f"롯데 자동화 오류: {str(e)}"
            logger.error(error_msg)
            self.update_automation_log(log, "failed", error_msg)
            return {"success": False, "message": error_msg}
    
    async def run_shilla_automation(self, account: DutyFreeAccount) -> Dict:
        """신라 면세점 자동화 실행"""
        log = self.create_automation_log(account, "running", "신라 자동화 시작")
        
        try:
            logger.info(f"신라 자동화 시작: {account.username}")
            
            if not ExcelProcessor:
                raise ImportError("신라 자동화 모듈이 없습니다")
            
            # 신라 RPA 실행 (사용자별 계정으로)
            excel_file_path = await self.run_shilla_rpa_with_account(account)
            
            if not excel_file_path or not os.path.exists(excel_file_path):
                self.update_automation_log(log, "failed", "엑셀 파일 다운로드 실패")
                return {"success": False, "message": "엑셀 파일 다운로드 실패"}
            
            # 엑셀 데이터 처리 및 DB 저장
            records_count = await self.save_shilla_data_to_db(excel_file_path, account.user_id)
            
            # 임시 파일 삭제
            try:
                os.remove(excel_file_path)
            except:
                pass
            
            self.update_automation_log(log, "success", f"데이터 수집 및 저장 완료", records_count)
            
            logger.info(f"신라 자동화 완료: {account.username} - {records_count}건")
            return {"success": True, "message": f"{records_count}건 처리 완료", "records_count": records_count}
            
        except Exception as e:
            error_msg = f"신라 자동화 오류: {str(e)}"
            logger.error(error_msg)
            self.update_automation_log(log, "failed", error_msg)
            return {"success": False, "message": error_msg}
    
    async def run_shilla_rpa_with_account(self, account: DutyFreeAccount) -> Optional[str]:
        """사용자별 신라 RPA 실행"""
        try:
            # 현재 사용자 홈 디렉터리 가져오기
            import pwd
            import getpass
            
            current_user = getpass.getuser()
            user_home = os.path.expanduser(f"~{current_user}")
            downloads_dir = os.path.join(user_home, "Downloads")
            
            logger.info(f"현재 사용자: {current_user}, 다운로드 디렉터리: {downloads_dir}")
            
            # 다운로드 디렉터리 생성 (없으면)
            os.makedirs(downloads_dir, exist_ok=True)
            
            # 신라 RPA 실행
            if shilla_main:
                result = await shilla_main()
                # 신라에서 다운로드한 파일 찾기
                possible_files = [
                    os.path.join(downloads_dir, 'shilla_report.xlsx'),
                    os.path.join(downloads_dir, 'shilla_data.xlsx'),
                    os.path.join(os.path.dirname(__file__), '..', '..', 'AUTOSHILLA', 'downloads', 'shilla_report.xlsx')
                ]
                
                for excel_path in possible_files:
                    if os.path.exists(excel_path):
                        logger.info(f"신라 엑셀 파일 발견: {excel_path}")
                        return excel_path
                
                logger.warning("신라 엑셀 파일을 찾을 수 없습니다")
            
            return None
            
        except Exception as e:
            logger.error(f"신라 RPA 실행 오류: {e}")
            return None
    
    async def save_lotte_data_to_db(self, data: List[Dict], user_id: int) -> int:
        """롯데 데이터를 DB에 저장"""
        db = self.get_db_session()
        try:
            # 기존 데이터 삭제 (해당 사용자만)
            db.query(LotteExcelData).filter(LotteExcelData.user_id == user_id).delete()
            
            records_count = 0
            for row in data:
                # LotteExcelData 객체 생성 (user_id 포함)
                excel_record = LotteExcelData(
                    user_id=user_id,
                    점구분=row.get('점구분'),
                    원매출일자=row.get('원매출일자'),
                    매출일자=row.get('매출일자'),
                    수입_로컬=row.get('수입/로컬'),
                    단체번호=row.get('단체번호'),
                    name=row.get('name'),
                    VIP번호=row.get('VIP번호'),
                    receiptNumber=row.get('receiptNumber'),
                    교환권상태=row.get('교환권상태'),
                    카테고리=row.get('카테고리'),
                    브랜드=row.get('브랜드'),
                    상품명=row.get('상품명'),
                    상품구분=row.get('상품구분'),
                    상품코드=row.get('상품코드'),
                    Ref_No=row.get('Ref.No'),
                    Color=row.get('Color'),
                    배송구분=row.get('배송구분'),
                    판매방식=row.get('판매방식'),
                    판매수량=row.get('판매수량'),
                    판매가_달러=row.get('판매가($)'),
                    총매출액_달러=row.get('총매출액($)'),
                    순매출액_달러=row.get('순매출액($)'),
                    할인액_달러=row.get('할인액($)'),
                    총매출액_원=row.get('총매출액(\\)'),
                    순매출액_원=row.get('순매출액(\\)'),
                    할인액_원=row.get('할인액(\\)')
                )
                db.add(excel_record)
                records_count += 1
            
            db.commit()
            logger.info(f"롯데 데이터 저장 완료: {records_count}건")
            return records_count
            
        except Exception as e:
            logger.error(f"롯데 데이터 저장 오류: {e}")
            db.rollback()
            raise e
    
    async def save_shilla_data_to_db(self, excel_file_path: str, user_id: int) -> int:
        """신라 엑셀 데이터를 DB에 저장"""
        db = self.get_db_session()
        try:
            # 엑셀 파일 처리
            processor = ExcelProcessor(excel_file_path)
            processed_data = processor.process_excel()
            
            if processed_data is None or processed_data.empty:
                raise ValueError("처리된 데이터가 없습니다")
            
            # 기존 데이터 삭제 (해당 사용자만)
            db.query(ShillaExcelData).filter(ShillaExcelData.user_id == user_id).delete()
            
            records_count = 0
            for _, row in processed_data.iterrows():
                # ShillaExcelData 객체 생성 (user_id 포함)
                excel_record = ShillaExcelData(
                    user_id=user_id,
                    No=str(row.get('No', '')),
                    점=str(row.get('점', '')),
                    원매출일자=str(row.get('원매출일자', '')),
                    매출일자=str(row.get('매출일자', '')),
                    여행사명=str(row.get('여행사명', '')),
                    여행사코드=str(row.get('여행사코드', '')),
                    그룹번호=str(row.get('그룹번호', '')),
                    대표가이드=str(row.get('대표가이드', '')),
                    출생연도=str(row.get('출생연도', '')),
                    name=str(row.get('name', '')),
                    receiptNumber=str(row.get('receiptNumber', '')),
                    BILL_상태=str(row.get('BILL 상태', '')),
                    상품위치=str(row.get('상품위치', '')),
                    카테고리=str(row.get('카테고리', '')),
                    브랜드명=str(row.get('브랜드명', '')),
                    상품명=str(row.get('상품명', '')),
                    상품코드=str(row.get('상품코드', '')),
                    판매가_달러=row.get('판매가($)'),
                    순매출액_원=row.get('순매출액(￦)'),
                    할인액_원=row.get('할인액(￦)')
                )
                db.add(excel_record)
                records_count += 1
            
            db.commit()
            logger.info(f"신라 데이터 저장 완료: {records_count}건")
            return records_count
            
        except Exception as e:
            logger.error(f"신라 데이터 저장 오류: {e}")
            db.rollback()
            raise e
    
    async def run_all_automations(self) -> Dict:
        """모든 활성화된 계정의 자동화 실행"""
        try:
            accounts = self.get_active_accounts()
            if not accounts:
                logger.info("실행할 활성화된 계정이 없습니다")
                return {"success": True, "message": "실행할 계정이 없습니다", "results": []}
            
            results = []
            
            # 롯데 계정들 먼저 실행 (API 방식으로 빠름)
            lotte_accounts = [acc for acc in accounts if acc.duty_free_type == "lotte"]
            for account in lotte_accounts:
                try:
                    result = await self.run_lotte_automation(account)
                    results.append({
                        "account_id": account.id,
                        "duty_free_type": account.duty_free_type,
                        "username": account.username,
                        "result": result
                    })
                except Exception as e:
                    logger.error(f"롯데 계정 {account.username} 자동화 오류: {e}")
                    results.append({
                        "account_id": account.id,
                        "duty_free_type": account.duty_free_type,
                        "username": account.username,
                        "result": {"success": False, "message": str(e)}
                    })
            
            # 신라 계정들 시간 간격을 두고 실행 (Playwright 충돌 방지)
            shilla_accounts = [acc for acc in accounts if acc.duty_free_type == "shilla"]
            for i, account in enumerate(shilla_accounts):
                try:
                    if i > 0:
                        # 이전 실행과 30분 간격
                        await asyncio.sleep(1800)  # 30분 = 1800초
                    
                    result = await self.run_shilla_automation(account)
                    results.append({
                        "account_id": account.id,
                        "duty_free_type": account.duty_free_type,
                        "username": account.username,
                        "result": result
                    })
                except Exception as e:
                    logger.error(f"신라 계정 {account.username} 자동화 오류: {e}")
                    results.append({
                        "account_id": account.id,
                        "duty_free_type": account.duty_free_type,
                        "username": account.username,
                        "result": {"success": False, "message": str(e)}
                    })
            
            # 결과 요약
            successful = len([r for r in results if r["result"]["success"]])
            total = len(results)
            
            logger.info(f"자동화 실행 완료: {successful}/{total} 성공")
            
            return {
                "success": True,
                "message": f"자동화 실행 완료: {successful}/{total} 성공",
                "results": results,
                "summary": {
                    "total": total,
                    "successful": successful,
                    "failed": total - successful
                }
            }
            
        except Exception as e:
            logger.error(f"전체 자동화 실행 오류: {e}")
            return {"success": False, "message": str(e)}
        finally:
            self.close_db_session()

# 전역 서비스 인스턴스
automation_service = UserAutomationService()