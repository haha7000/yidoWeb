import requests
import time

class LotteAPI:
    def __init__(self, session, base_url, auth):
        self.session = session
        self.base_url = base_url
        self.auth = auth
    
    def fetch_brand_sales(self, tay_cd="301912", tay_nm="(주)혜신리츠"):
        """브랜드별 매출 데이터 조회"""
        url = f"{self.base_url}/min08/service/salprom/srm/salesmgt/taycrdaysalesinqry/TayCrdaySalesInqryController/TayCrdaySalesByBrndInqry"
        
        payload = self._build_sales_payload(tay_cd, tay_nm)
        headers = self._get_api_headers()
        
        return self._make_api_request(url, payload, headers, "브랜드별")
    
    def fetch_product_sales(self, tay_cd="301912", tay_nm="주식회사&#32;혜신"):
        """상품별 매출 데이터 조회 (prdcd, prodNm 포함)"""
        url = f"{self.base_url}/min08/service/salprom/srm/salesmgt/taycrdaysalesinqry/TayCrdaySalesInqryController/TayCrdaySalesByProdInqry"
        
        payload = self._build_sales_payload(tay_cd, tay_nm)
        headers = self._get_api_headers()
        
        return self._make_api_request(url, payload, headers, "상품별")
    
    def _build_sales_payload(self, tay_cd, tay_nm):
        """매출 조회 페이로드 생성"""
        current_timestamp = str(int(time.time() * 1000))
        
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<Root xmlns="http://www.nexacroplatform.com/platform/dataset">
  <Parameters>
    <Parameter id="L-VISITOR">{getattr(self.auth, 'l_visitor', '')}</Parameter>
    <Parameter id="gv_ldfstatustime">{getattr(self.auth, 'gv_statustime', current_timestamp)}</Parameter>
    <Parameter id="custInfoMgtYn" />
    <Parameter id="xnyksamnu">MA==</Parameter>
    <Parameter id="xdirsu">VDMwMTkxMg==</Parameter>
  </Parameters>
  <Dataset id="ds_search">
    <ColumnInfo>
      <Column id="grpTypeCd" type="STRING" size="256" />
      <Column id="catecd" type="STRING" size="256" />
      <Column id="brndcd" type="STRING" size="256" />
      <Column id="brndNm" type="STRING" size="256" />
      <Column id="imptLocalDvsCd" type="STRING" size="256" />
      <Column id="tayCd" type="STRING" size="256" />
      <Column id="tayNm" type="STRING" size="256" />
      <Column id="gdecd" type="STRING" size="256" />
      <Column id="gdeNm" type="STRING" size="256" />
      <Column id="exchNo" type="STRING" size="256" />
      <Column id="typeCd" type="STRING" size="256" />
      <Column id="psptno" type="STRING" size="256" />
      <Column id="grpNo" type="STRING" size="256" />
      <Column id="prdcd" type="STRING" size="256" />
      <Column id="prodNm" type="STRING" size="256" />
      <Column id="rcrtcustRgnCd" type="STRING" size="256" />
    </ColumnInfo>
    <Rows>
      <Row>
        <Col id="tayCd">{tay_cd}</Col>
        <Col id="tayNm">{tay_nm}</Col>
      </Row>
    </Rows>
  </Dataset>
  <Dataset id="ds_strTemp">
    <ColumnInfo>
      <Column id="_chk" type="STRING" size="256" />
      <Column id="strCd" type="STRING" size="256" />
      <Column id="strNm" type="STRING" size="256" />
      <Column id="sortSeq" type="STRING" size="256" />
    </ColumnInfo>
    <Rows>
      <Row><Col id="_chk">1</Col><Col id="strCd">901</Col><Col id="strNm">명동본점</Col></Row>
      <Row><Col id="_chk">1</Col><Col id="strCd">902</Col><Col id="strNm">월드타워</Col></Row>
      <Row><Col id="_chk">1</Col><Col id="strCd">90S</Col><Col id="strNm">코엑스</Col></Row>
      <Row><Col id="_chk">1</Col><Col id="strCd">908</Col><Col id="strNm">부산</Col></Row>
      <Row><Col id="_chk">1</Col><Col id="strCd">90G</Col><Col id="strNm">제주</Col></Row>
      <Row><Col id="_chk">1</Col><Col id="strCd">909</Col><Col id="strNm">김해공항</Col></Row>
      <Row><Col id="_chk">1</Col><Col id="strCd">905</Col><Col id="strNm">인천공항T1</Col></Row>
      <Row><Col id="_chk">1</Col><Col id="strCd">90L</Col><Col id="strNm">인천공항T2</Col></Row>
      <Row><Col id="_chk">1</Col><Col id="strCd">90C</Col><Col id="strNm">김포공항</Col></Row>
    </Rows>
  </Dataset>
</Root>'''
    
    def _get_api_headers(self):
        """API 요청 헤더 생성"""
        return {
            'Content-Type': 'text/xml',
            'Accept': 'application/xml, text/xml, */*',
            'Origin': 'https://srm.lottedfs.co.kr',
            'Referer': 'https://srm.lottedfs.co.kr/ui/ldfs_ui/index.html',
            'X-Requested-With': 'Fetch',
            'uiId': 'MP030213M01',
            'guid': '20250430UIFT301912____14355574342060001',
        }
    
    def _make_api_request(self, url, payload, headers, request_type):
        """API 요청 실행"""
        try:
            response = self.session.post(url, data=payload, headers=headers)
            
            if response.status_code == 200:
                print(f"✅ {request_type} 매출 데이터 응답 수신 성공 (길이: {len(response.text)} bytes)")
                return response.text
            else:
                print(f"❌ {request_type} 매출 조회 실패: {response.status_code}")
                print(f"응답: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ 네트워크 오류: {str(e)}")
            return None