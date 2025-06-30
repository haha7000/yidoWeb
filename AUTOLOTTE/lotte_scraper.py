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
    
    def fetch_brand_sales(self, tay_cd="301912", tay_nm="(주)혜신리츠"):
        """브랜드별 매출 데이터 조회"""
        xml_response = self.api.fetch_brand_sales(tay_cd, tay_nm)
        if xml_response:
            sales_data = self.parser.parse_sales_xml(xml_response)
            self.latest_sales_data = sales_data
            return sales_data
        return None
    
    def fetch_product_sales(self, tay_cd="301912", tay_nm="주식회사&#32;혜신"):
        """상품별 매출 데이터 조회 (prdcd, prodNm 포함)"""
        xml_response = self.api.fetch_product_sales(tay_cd, tay_nm)
        if xml_response:
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