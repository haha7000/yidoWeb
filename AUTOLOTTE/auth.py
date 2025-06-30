import requests
import xml.etree.ElementTree as ET
import time
import secrets

class LotteAuth:
    def __init__(self, session, base_url):
        self.session = session
        self.base_url = base_url
        self.l_visitor = None
        self.gv_statustime = None
    
    def login(self, user_id, password):
        """로그인 수행"""
        # 1. 메인 페이지 접근
        login_page_url = f"{self.base_url}/ui/ldfs_ui/index.html"
        response = self.session.get(login_page_url)
        print(f"메인 페이지 접근: {response.status_code}")
        
        # 2. 토큰 생성
        self.l_visitor = secrets.token_urlsafe(12)[:12]
        self.gv_statustime = str(int(time.time() * 1000))
        
        # 3. 로그인 API 호출
        login_api_url = f"{self.base_url}/min01/service/cmntech/cmnbiznesmgt/login/loginmgt/LoginMgtController/prcsLogin"
        
        payload = self._build_login_payload(user_id, password)
        headers = {
            'Content-Type': 'text/xml',
            'Accept': 'application/xml, text/xml, */*',
            'Origin': self.base_url,
            'Referer': f"{self.base_url}/ui/ldfs_ui/index.html",
            'X-Requested-With': 'Fetch',
        }
        
        try:
            login_response = self.session.post(login_api_url, data=payload, headers=headers)
            
            if login_response.status_code == 200:
                print("✅ 로그인 요청 성공")
                
                try:
                    ET.fromstring(login_response.text)
                    print("✅ 로그인 성공 - 세션 정보 저장됨")
                    return True
                except ET.ParseError:
                    print("❌ 로그인 응답 파싱 실패")
                    return False
            else:
                print(f"❌ 로그인 실패: {login_response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ 로그인 네트워크 오류: {str(e)}")
            return False
    
    def _build_login_payload(self, user_id, password):
        """로그인 페이로드 생성"""
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<Root xmlns="http://www.nexacroplatform.com/platform/dataset">
  <Parameters>
    <Parameter id="L-VISITOR">{self.l_visitor}</Parameter>
    <Parameter id="gv_openArgs" />
    <Parameter id="gv_ldfstatustime">{self.gv_statustime}</Parameter>
    <Parameter id="bufSize" />
    <Parameter id="custInfoMgtYn" />
    <Parameter id="xnyksamnu">MA==</Parameter>
    <Parameter id="xdirsu" />
  </Parameters>
  <Dataset id="ds_search">
    <ColumnInfo>
      <Column id="usrId" type="STRING" size="256" />
      <Column id="pwd" type="STRING" size="256" />
      <Column id="sysDvsCd" type="STRING" size="256" />
      <Column id="visibleType" type="STRING" size="256" />
      <Column id="usrOtpNum" type="STRING" size="256" />
      <Column id="langCd" type="STRING" size="256" />
      <Column id="autoLoginYn" type="STRING" size="256" />
      <Column id="usrIp" type="STRING" size="256" />
      <Column id="newLoginYn" type="STRING" size="256" />
    </ColumnInfo>
    <Rows>
      <Row>
        <Col id="usrId">{user_id}</Col>
        <Col id="pwd">{password}</Col>
        <Col id="sysDvsCd">11</Col>
        <Col id="usrOtpNum" />
        <Col id="langCd">KO</Col>
      </Row>
    </Rows>
  </Dataset>
</Root>'''
    
    def manual_cookie_setup(self, cookie_string, l_visitor, gv_statustime):
        """수동 쿠키 설정"""
        for cookie_pair in cookie_string.split('; '):
            if '=' in cookie_pair:
                name, value = cookie_pair.split('=', 1)
                self.session.cookies.set(name, value, domain='.lottedfs.co.kr')
        
        self.l_visitor = l_visitor
        self.gv_statustime = gv_statustime
        print("✅ 쿠키 설정 완료")