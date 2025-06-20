#!/usr/bin/env python3
"""
수령증 생성 및 다운로드 서비스
"""

import os
import shutil
import zipfile
from datetime import datetime
from typing import List, Dict, Optional
from openpyxl import load_workbook
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.models import ProcessingHistory
from app.core.config import settings
import tempfile

class ReceiptService:
    """수령증 생성 및 다운로드 서비스"""
    
    def __init__(self):
        # 설정에서 엑셀 템플릿 경로 가져오기
        self.template_path = os.path.join(settings.excel_template_dir, "수령증양식.xlsx")
        
    def generate_receipt_for_customer(self, upload_id: str, customer_name: str, user_id: int) -> Optional[str]:
        """특정 고객의 수령증 생성"""
        try:
            db = SessionLocal()
            
            # 고객 데이터 조회
            customer_data = self._get_customer_data(db, upload_id, customer_name, user_id)
            if not customer_data:
                print(f"고객 데이터를 찾을 수 없습니다: {customer_name}")
                return None
            
            # 임시 디렉토리에 수령증 생성
            temp_dir = tempfile.mkdtemp()
            receipt_path = os.path.join(temp_dir, f"{customer_name}의 수령증.xlsx")
            
            # 수령증 생성
            success = self._create_receipt_file(customer_data, receipt_path)
            
            db.close()
            
            if success:
                return receipt_path
            else:
                return None
            
        except Exception as e:
            print(f"고객 수령증 생성 오류: {e}")
            return None
    
    def generate_receipts_for_session(self, upload_id: str, user_id: int) -> Optional[str]:
        """세션의 모든 고객 수령증 생성 (ZIP 파일)"""
        try:
            db = SessionLocal()
            
            # 세션의 모든 고객 데이터 조회
            customers_data = self._get_session_customers_data(db, upload_id, user_id)
            if not customers_data:
                print(f"세션 데이터를 찾을 수 없습니다: {upload_id}")
                return None
            
            # 임시 디렉토리 생성
            temp_dir = tempfile.mkdtemp()
            
            # 각 고객별 수령증 생성
            receipt_files = []
            for customer_data in customers_data:
                customer_name = customer_data['excel_name']
                if customer_name:
                    receipt_file = os.path.join(temp_dir, f"{customer_name}의 수령증.xlsx")
                    if self._create_receipt_file(customer_data, receipt_file):
                        receipt_files.append(receipt_file)
            
            if not receipt_files:
                print("생성된 수령증이 없습니다.")
                return None
            
            # ZIP 파일 생성
            zip_path = os.path.join(temp_dir, "수령증.zip")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for receipt_file in receipt_files:
                    zipf.write(receipt_file, os.path.basename(receipt_file))
            
            db.close()
            return zip_path
            
        except Exception as e:
            print(f"세션 수령증 생성 오류: {e}")
            return None
    
    def _get_customer_data(self, db: Session, upload_id: str, customer_name: str, user_id: int) -> Optional[Dict]:
        """특정 고객의 데이터 조회"""
        try:
            # processing_history에서 고객 데이터 조회
            query = text("""
                SELECT 
                    excel_name,
                    passport_number,
                    birthday,
                    duty_free_type,
                    upload_id
                FROM processing_history 
                WHERE upload_id = :upload_id 
                AND excel_name = :customer_name 
                AND user_id = :user_id
                AND is_matched = true
                LIMIT 1
            """)
            
            result = db.execute(query, {
                "upload_id": upload_id,
                "customer_name": customer_name,
                "user_id": user_id
            }).fetchone()
            
            if not result:
                return None
            
            # commission_total 조회
            commission_total = self._get_commission_total(db, upload_id, customer_name, user_id, result.duty_free_type)
            
            return {
                'excel_name': result.excel_name,
                'passport_number': result.passport_number,
                'birthday': result.birthday,
                'commission_total': commission_total,
                'duty_free_type': result.duty_free_type
            }
            
        except Exception as e:
            print(f"고객 데이터 조회 오류: {e}")
            return None
    
    def _get_session_customers_data(self, db: Session, upload_id: str, user_id: int) -> List[Dict]:
        """세션의 모든 고객 데이터 조회"""
        try:
            # 고객별로 그룹화하여 조회
            query = text("""
                SELECT DISTINCT
                    excel_name,
                    passport_number,
                    birthday,
                    duty_free_type
                FROM processing_history 
                WHERE upload_id = :upload_id 
                AND user_id = :user_id
                AND is_matched = true
                AND excel_name IS NOT NULL
                ORDER BY excel_name
            """)
            
            results = db.execute(query, {
                "upload_id": upload_id,
                "user_id": user_id
            }).fetchall()
            
            customers_data = []
            for result in results:
                # 각 고객의 commission_total 조회
                commission_total = self._get_commission_total(db, upload_id, result.excel_name, user_id, result.duty_free_type)
                
                customers_data.append({
                    'excel_name': result.excel_name,
                    'passport_number': result.passport_number,
                    'birthday': result.birthday,
                    'commission_total': commission_total,
                    'duty_free_type': result.duty_free_type
                })
            
            return customers_data
            
        except Exception as e:
            print(f"세션 고객 데이터 조회 오류: {e}")
            return []
    
    def _get_commission_total(self, db: Session, upload_id: str, customer_name: str, user_id: int, duty_free_type: str) -> float:
        """고객의 총 수수료 조회 - processing_history에서 직접 조회"""
        try:
            # processing_history 테이블에서 직접 수수료 합계 조회
            query = text("""
                SELECT SUM(commission_fee) as total_commission
                FROM processing_history 
                WHERE upload_id = :upload_id 
                AND excel_name = :customer_name
                AND user_id = :user_id
                AND is_matched = true
                AND commission_fee IS NOT NULL
            """)
            
            result = db.execute(query, {
                "upload_id": upload_id,
                "customer_name": customer_name,
                "user_id": user_id
            }).fetchone()
            
            if result and result.total_commission:
                return float(result.total_commission)
            else:
                print(f"수수료 데이터 없음: upload_id={upload_id}, customer={customer_name}")
                return 0.0
            
        except Exception as e:
            print(f"수수료 조회 오류: {e}")
            import traceback
            traceback.print_exc()
            return 0.0
    
    def _create_receipt_file(self, customer_data: Dict, output_path: str) -> bool:
        """수령증 파일 생성"""
        try:
            # 템플릿 파일 복사
            shutil.copy2(self.template_path, output_path)
            
            # 엑셀 파일 열기
            workbook = load_workbook(output_path)
            worksheet = workbook['수령증']
            
            # 데이터 입력
            # D7: 성명
            worksheet['D7'] = customer_data.get('excel_name', '')
            
            # D8: 여권번호
            worksheet['D8'] = customer_data.get('passport_number', '')
            
            # D9: 생년월일
            birthday = customer_data.get('birthday')
            if birthday:
                if isinstance(birthday, str):
                    worksheet['D9'] = birthday
                else:
                    worksheet['D9'] = birthday.strftime('%Y-%m-%d')
            
            # D10: 현금 지급금액
            commission_total = customer_data.get('commission_total', 0)
            worksheet['D10'] = f"{commission_total:,.0f}원"
            
            # B16:D16: 현재 날짜
            now = datetime.now()
            date_str = f"{now.year}년           {now.month:02d}월          {now.day:02d}일"
            worksheet['B16'] = date_str
            
            # B19:D19: 수령자
            customer_name = customer_data.get('excel_name', '')
            receiver_str = f"수령자(收款人签字）：    {customer_name}    （인)"
            worksheet['B19'] = receiver_str
            
            # 파일 저장
            workbook.save(output_path)
            workbook.close()
            
            print(f"수령증 생성 완료: {output_path}")
            return True
            
        except Exception as e:
            print(f"수령증 파일 생성 오류: {e}")
            return False 