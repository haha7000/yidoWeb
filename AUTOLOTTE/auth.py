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
        # 로그인 정보 저장 (재로그인용)
        self.user_id = None
        self.password = None
        self.is_logged_in = False
    
    def login(self, user_id, password):
        """로그인 수행"""
        # 로그인 정보 저장
        self.user_id = user_id
        self.password = password
        
        return self._perform_login(user_id, password)
    
    def _perform_login(self, user_id, password):
        """실제 로그인 수행"""
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
                    self.is_logged_in = True
                    
                    # 세션 쿠키 확인
                    print(f"🔍 세션 쿠키 수: {len(self.session.cookies)}")
                    for cookie in self.session.cookies:
                        print(f"  - {cookie.name}: {cookie.value[:20]}...")
                    
                    # 로그인 후 잠시 대기 (세션 설정 완료 대기)
                    print("⏳ 세션 설정 완료 대기 중...")
                    time.sleep(3)
                    
                    return True
                except ET.ParseError:
                    print("❌ 로그인 응답 파싱 실패")
                    self.is_logged_in = False
                    return False
            else:
                print(f"❌ 로그인 실패: {login_response.status_code}")
                self.is_logged_in = False
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ 로그인 네트워크 오류: {str(e)}")
            self.is_logged_in = False
            return False
    
    def refresh_session(self):
        """세션 갱신 (재로그인)"""
        if not self.user_id or not self.password:
            print("❌ 저장된 로그인 정보가 없어 세션 갱신할 수 없습니다")
            return False
        
        print("🔄 세션 만료로 재로그인 시도 중...")
        
        # 기존 세션 쿠키 초기화
        self.session.cookies.clear()
        self.is_logged_in = False
        
        # 재로그인 수행
        success = self._perform_login(self.user_id, self.password)
        
        if success:
            print("✅ 세션 갱신 성공")
        else:
            print("❌ 세션 갱신 실패")
        
        return success
    
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
    
    def validate_session(self):
        """세션 유효성 검증"""
        try:
            # 현재 세션의 모든 쿠키 출력
            print(f"🔍 현재 세션 쿠키 수: {len(self.session.cookies)}")
            for cookie in self.session.cookies:
                print(f"  - {cookie.name}: {cookie.value[:30]}... (도메인: {cookie.domain})")
            
            # 간단한 세션 확인 API 호출
            check_url = f"{self.base_url}/ui/ldfs_ui/index.html"
            response = self.session.get(check_url)
            
            if response.status_code == 200:
                # 세션 쿠키 확인
                session_cookies = [c for c in self.session.cookies if 'SESSION' in c.name]
                if session_cookies:
                    print(f"✅ 세션 유효성 확인됨 (쿠키: {len(session_cookies)}개)")
                    return True
                else:
                    print("❌ 세션 쿠키 없음")
                    return False
            else:
                print(f"❌ 세션 확인 실패: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 세션 검증 중 오류: {e}")
            return False