import requests
from auth import LotteAuth
from api import LotteAPI
from parser import LotteParser
from exporter import LotteExporter

class LotteDutyFreeSales:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://srm.lottedfs.co.kr"
        self.latest_sales_data = []
        
        # 각 기능별 클래스 초기화
        self.auth = LotteAuth(self.session, self.base_url)
        self.api = LotteAPI(self.session, self.base_url, self.auth)
        self.parser = LotteParser()
        self.exporter = LotteExporter()
    
    def login(self, user_id, password):
        """로그인"""
        return self.auth.login(user_id, password)
    
    def manual_cookie_setup(self, cookie_string, l_visitor, gv_statustime):
        """수동 쿠키 설정"""
        self.auth.manual_cookie_setup(cookie_string, l_visitor, gv_statustime)
    
    def _fetch_with_session_retry(self, fetch_func, *args, **kwargs):
        """세션 재시도 로직이 포함된 데이터 조회"""
        # 첫 번째 시도
        result = fetch_func(*args, **kwargs)
        
        # 세션 만료 확인 및 재시도
        if result is None and self._is_session_expired():
            print("🔄 세션 만료 감지, 자동 갱신 시도...")
            
            # 세션 갱신 시도
            if self.auth.refresh_session():
                print("🔄 세션 갱신 후 재시도...")
                # 갱신 후 재시도
                result = fetch_func(*args, **kwargs)
            else:
                print("❌ 세션 갱신 실패")
        
        return result
    
    def _is_session_expired(self):
        """세션 만료 여부 확인"""
        # 최근 API 응답에서 세션 만료 키워드 확인
        # 실제로는 API 응답을 파싱해서 확인해야 하지만,
        # 여기서는 간단히 세션 유효성만 체크
        return not self.auth.validate_session()
    
    def fetch_brand_sales(self, tay_cd="301912", tay_nm="(주)혜신리츠"):
        """브랜드별 매출 데이터 조회"""
        return self._fetch_with_session_retry(self._fetch_brand_sales_internal, tay_cd, tay_nm)
    
    def _fetch_brand_sales_internal(self, tay_cd="301912", tay_nm="(주)혜신리츠"):
        """브랜드별 매출 데이터 조회 (내부 구현)"""
        # 세션 유효성 검증
        if not self.auth.validate_session():
            print("❌ 세션이 유효하지 않습니다")
            return None
            
        xml_response = self.api.fetch_brand_sales(tay_cd, tay_nm)
        if xml_response:
            # API 레벨에서 이미 세션 만료를 확인했으므로 여기서는 제거
            sales_data = self.parser.parse_sales_xml(xml_response)
            self.latest_sales_data = sales_data
            return sales_data
        return None
    
    def fetch_product_sales(self, tay_cd="301912", tay_nm="주식회사&#32;혜신"):
        """상품별 매출 데이터 조회 (prdcd, prodNm 포함)"""
        return self._fetch_with_session_retry(self._fetch_product_sales_internal, tay_cd, tay_nm)
    
    def _fetch_product_sales_internal(self, tay_cd="301912", tay_nm="주식회사&#32;혜신"):
        """상품별 매출 데이터 조회 (내부 구현)"""
        # 세션 유효성 검증
        if not self.auth.validate_session():
            print("❌ 세션이 유효하지 않습니다")
            return None
            
        xml_response = self.api.fetch_product_sales(tay_cd, tay_nm)
        if xml_response:
            # API 레벨에서 이미 세션 만료를 확인했으므로 여기서는 제거
            sales_data = self.parser.parse_sales_xml(xml_response)
            self.latest_sales_data = sales_data
            
            # 상품 정보 포함 여부 확인
            self.exporter.check_product_info(sales_data)
            
            return sales_data
        return None
    
    def save_to_excel(self, sales_data=None, filename=None):
        """엑셀 파일 저장"""
        if sales_data is None:
            sales_data = self.latest_sales_data
        
        return self.exporter.save_to_excel(sales_data, filename)
    
    def get_latest_data(self):
        """최근 조회된 데이터 반환"""
        return self.latest_sales_data