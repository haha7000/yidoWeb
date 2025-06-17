from app.models.models import ReceiptMatchLog
from app.core.database import SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy import text
from decimal import Decimal
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class CommissionService:
    """할인율 및 수수료 계산 서비스"""
    
    def __init__(self):
        self.session = SessionLocal()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()
    
    def calculate_and_update_all_commissions(self, user_id: int = None) -> dict:
        """모든 매칭된 데이터에 대해 할인율과 수수료를 계산하고 업데이트"""
        try:
            # 매칭된 데이터만 조회 (is_matched = True) - duty_free_type 추가
            query = """
            SELECT id, user_id, receipt_number, discount_amount_krw, sales_price_usd, 
                   net_sales_krw, sales_date, category, brand, product_code, store_branch, duty_free_type
            FROM receipt_match_log 
            WHERE is_matched = TRUE 
            AND discount_amount_krw IS NOT NULL 
            AND sales_price_usd IS NOT NULL 
            AND net_sales_krw IS NOT NULL
            """
            
            if user_id:
                query += f" AND user_id = {user_id}"
            
            query += " ORDER BY user_id, receipt_number"
            
            result = self.session.execute(text(query)).fetchall()
            
            if not result:
                return {
                    "success": True,
                    "message": "계산할 매칭된 데이터가 없습니다.",
                    "processed_count": 0
                }
            
            processed_count = 0
            error_count = 0
            
            for row in result:
                try:
                    # 할인율 계산 및 업데이트
                    self._calculate_and_update_single_record(row)
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"영수증 {row.receipt_number} 처리 중 오류: {e}")
                    error_count += 1
                    continue
            
            # 변경사항 커밋
            self.session.commit()
            
            return {
                "success": True,
                "message": f"할인율 및 수수료 계산 완료",
                "processed_count": processed_count,
                "error_count": error_count,
                "total_records": len(result)
            }
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"할인율 및 수수료 계산 중 오류: {e}")
            return {
                "success": False,
                "message": f"계산 중 오류가 발생했습니다: {str(e)}",
                "processed_count": 0
            }
    
    def _calculate_and_update_single_record(self, row) -> None:
        """단일 레코드에 대해 할인율과 수수료를 계산하고 업데이트"""
        record_id, user_id, receipt_number, discount_amount_krw, sales_price_usd, net_sales_krw, sales_date, category, brand, product_code, store_branch, duty_free_type = row
        
        # 1. 할인율 계산: (할인액 / 판매가) × 100
        discount_rate = None
        if discount_amount_krw and sales_price_usd and sales_price_usd > 0:
            # 환율 고려하여 계산 (USD를 KRW로 변환하거나 비율로 계산)
            # 현재는 원화 할인액과 달러 판매가 비교이므로 비율로 계산
            # 간단하게 할인액/순매출액 비율로 계산하여 %로 변환
            if net_sales_krw and net_sales_krw > 0:
                discount_rate = (float(discount_amount_krw) / float(net_sales_krw)) * 100
                discount_rate = round(discount_rate, 2)
        
        # 2. 수수료 계산
        commission_fee = None
        commission_rate = self._get_commission_rate(
            sales_date=sales_date,
            user_id=user_id,
            store_branch=store_branch,
            category=category,
            brand=brand,
            product_code=product_code,
            duty_free_type=duty_free_type  # 면세점 타입 추가
        )
        
        if commission_rate and net_sales_krw:
            commission_fee = float(net_sales_krw) * float(commission_rate)
            commission_fee = round(commission_fee, 2)
        
        # 3. 데이터베이스 업데이트
        update_sql = """
        UPDATE receipt_match_log 
        SET discount_rate = :discount_rate,
            commission_fee = :commission_fee
        WHERE id = :record_id
        """
        
        self.session.execute(text(update_sql), {
            "discount_rate": discount_rate,
            "commission_fee": commission_fee,
            "record_id": record_id
        })
        
        logger.info(f"영수증 {receipt_number}: 할인율={discount_rate}%, 수수료={commission_fee}원")
    
    def _get_commission_rate(self, sales_date, user_id: int, store_branch: str, 
                           category: str, brand: str, product_code: str, 
                           duty_free_type: str = None) -> Optional[Decimal]:
        """
        우선순위별로 수수료율을 조회
        1순위: product_code → item_fees
        2순위: brand → brand_fees  
        3순위: category → category_fees
        """
        
        # 면세점명 매핑 (duty_free_type 우선, 없으면 store_branch에서 추정)
        if duty_free_type:
            company_name = duty_free_type.upper() if duty_free_type.lower() in ['lotte', 'shilla'] else None
        else:
            company_name = self._get_company_name_from_branch(store_branch)
        
        if not company_name:
            logger.warning(f"면세점명을 찾을 수 없습니다: duty_free_type={duty_free_type}, store_branch={store_branch}")
            return None
        
        # fee_settings에서 해당 면세점, 지점, 날짜에 맞는 설정 조회
        settings_query = """
        SELECT id, free_rate_threshold 
        FROM fee_settings 
        WHERE company_name = :company_name
        AND branch_name = :branch_name
        AND :sales_date BETWEEN effective_from AND COALESCE(effective_to, '2099-12-31')
        ORDER BY effective_from DESC
        LIMIT 1
        """
        
        settings_result = self.session.execute(text(settings_query), {
            "company_name": company_name,
            "branch_name": store_branch,
            "sales_date": sales_date
        }).first()
        
        if not settings_result:
            logger.warning(f"수수료 설정을 찾을 수 없습니다: {company_name}, {store_branch}, {sales_date}")
            return None
        
        settings_id, free_rate_threshold = settings_result
        
        # 수수료 제외 임계값 확인 (할인율이 임계값 이상이면 수수료 0%)
        current_discount_rate = None
        if hasattr(self, '_current_discount_rate'):
            current_discount_rate = self._current_discount_rate
        
        if current_discount_rate and free_rate_threshold:
            if current_discount_rate >= float(free_rate_threshold) * 100:  # 임계값이 소수점이므로 100을 곱함
                logger.info(f"할인율 {current_discount_rate}%가 임계값 {float(free_rate_threshold)*100}% 이상이므로 수수료 0%")
                return Decimal('0.0')
        
        # 1순위: product_code로 item_fees 조회
        if product_code:
            item_query = """
            SELECT commission_rate 
            FROM item_fees 
            WHERE settings_id = :settings_id 
            AND product_code = :product_code
            LIMIT 1
            """
            
            item_result = self.session.execute(text(item_query), {
                "settings_id": settings_id,
                "product_code": str(product_code)
            }).first()
            
            if item_result:
                logger.info(f"상품코드 {product_code}로 수수료율 발견: {item_result[0]}")
                return item_result[0]
        
        # 2순위: brand로 brand_fees 조회
        if brand:
            brand_query = """
            SELECT commission_rate 
            FROM brand_fees 
            WHERE settings_id = :settings_id 
            AND brand_name = :brand_name
            LIMIT 1
            """
            
            brand_result = self.session.execute(text(brand_query), {
                "settings_id": settings_id,
                "brand_name": brand
            }).first()
            
            if brand_result:
                logger.info(f"브랜드 {brand}로 수수료율 발견: {brand_result[0]}")
                return brand_result[0]
        
        # 3순위: category로 category_fees 조회
        if category:
            category_query = """
            SELECT commission_rate 
            FROM category_fees 
            WHERE settings_id = :settings_id 
            AND category_code = :category_code
            LIMIT 1
            """
            
            category_result = self.session.execute(text(category_query), {
                "settings_id": settings_id,
                "category_code": category
            }).first()
            
            if category_result:
                logger.info(f"카테고리 {category}로 수수료율 발견: {category_result[0]}")
                return category_result[0]
        
        logger.warning(f"수수료율을 찾을 수 없습니다: 상품코드={product_code}, 브랜드={brand}, 카테고리={category}")
        return None
    
    def _get_company_name_from_branch(self, store_branch: str) -> Optional[str]:
        """점포구분으로부터 면세점명을 추정"""
        if not store_branch:
            return None
        
        store_branch_lower = store_branch.lower()
        
        # 롯데 관련 키워드
        lotte_keywords = ['롯데', 'lotte', '명동', '본점', '인천공항', '김포공항']
        if any(keyword in store_branch_lower for keyword in lotte_keywords):
            return 'LOTTE'
        
        # 신라 관련 키워드  
        shilla_keywords = ['신라', 'shilla', '인천', '공항']
        if any(keyword in store_branch_lower for keyword in shilla_keywords):
            return 'SHILLA'
        
        # 현대 관련 키워드
        hyundai_keywords = ['현대', 'hyundai']
        if any(keyword in store_branch_lower for keyword in hyundai_keywords):
            return 'HYUNDAI'
        
        # 기본값으로 LOTTE 반환 (기존 데이터가 주로 롯데)
        return 'LOTTE'
    
    def get_commission_summary(self, user_id: int = None) -> dict:
        """수수료 계산 결과 요약 조회"""
        try:
            query = """
            SELECT 
                COUNT(*) as total_matched,
                COUNT(CASE WHEN discount_rate IS NOT NULL THEN 1 END) as calculated_discount,
                COUNT(CASE WHEN commission_fee IS NOT NULL THEN 1 END) as calculated_commission,
                ROUND(AVG(discount_rate), 2) as avg_discount_rate,
                ROUND(SUM(commission_fee), 2) as total_commission_fee,
                ROUND(SUM(net_sales_krw), 2) as total_net_sales
            FROM receipt_match_log 
            WHERE is_matched = TRUE
            """
            
            if user_id:
                query += f" AND user_id = {user_id}"
            
            result = self.session.execute(text(query)).first()
            
            return {
                "success": True,
                "summary": {
                    "total_matched_records": result[0] or 0,
                    "calculated_discount_count": result[1] or 0,
                    "calculated_commission_count": result[2] or 0,
                    "average_discount_rate": float(result[3]) if result[3] else 0.0,
                    "total_commission_fee": float(result[4]) if result[4] else 0.0,
                    "total_net_sales": float(result[5]) if result[5] else 0.0
                }
            }
            
        except Exception as e:
            logger.error(f"수수료 요약 조회 중 오류: {e}")
            return {
                "success": False,
                "message": f"요약 조회 중 오류가 발생했습니다: {str(e)}"
            }

def calculate_discounts_and_commissions(user_id: int = None):
    """할인율과 수수료 계산 실행 함수"""
    with CommissionService() as service:
        return service.calculate_and_update_all_commissions(user_id)

def get_commission_summary(user_id: int = None):
    """수수료 계산 결과 요약 조회 함수"""
    with CommissionService() as service:
        return service.get_commission_summary(user_id) 