"""
면세점 계정 검증 서비스
롯데/신라 면세점 계정의 로그인 유효성을 검증
"""
import asyncio
import requests
import xml.etree.ElementTree as ET
import time
import secrets
from playwright.async_api import async_playwright
from typing import Dict, Tuple
import logging

# 로깅 설정
logger = logging.getLogger(__name__)

class LotteAccountValidator:
    """롯데 면세점 계정 검증 클래스"""
    
    def __init__(self, dev_mode: bool = False):
        self.base_url = "https://srm.lottedfs.co.kr"
        self.session = requests.Session()
        self.dev_mode = dev_mode
        
        # 세션 설정 (AUTOLOTTE와 동일하게)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def validate_account(self, username: str, password: str) -> Tuple[bool, str]:
        """롯데 계정 유효성 검증 (AUTOLOTTE 로직 사용)"""
        try:
            logger.info(f"롯데 계정 검증 시작: {username}")
            
            # 개발 모드에서는 더미 응답 반환
            if self.dev_mode:
                logger.info(f"개발 모드: 롯데 계정 {username} 검증 스킵")
                if username in ["T301912", "test123", "admin"]:
                    return True, "개발 모드: 계정 검증 성공"
                else:
                    return False, "개발 모드: 잘못된 테스트 계정"
            
            # AUTOLOTTE의 실제 로그인 로직 사용
            from AUTOLOTTE.lotte_scraper import LotteDutyFreeSales
            
            scraper = LotteDutyFreeSales()
            login_result = scraper.login(username, password)
            
            if login_result:
                logger.info("로그인 단계 통과, 실제 데이터 조회로 검증 진행...")
                
                # 실제 데이터 조회를 시도해서 인증이 정말 성공했는지 확인
                try:
                    # 간단한 브랜드별 매출 조회 시도
                    sales_data = scraper.fetch_brand_sales()
                    if sales_data and len(sales_data) >= 0:  # 빈 배열도 성공으로 간주
                        logger.info(f"롯데 계정 검증 성공: {username} (데이터 조회 성공)")
                        return True, "로그인 성공"
                    else:
                        logger.warning(f"롯데 계정 검증 실패: {username} (데이터 조회 실패)")
                        return False, "로그인 실패: 데이터 접근 권한이 없습니다"
                        
                except Exception as e:
                    logger.warning(f"롯데 데이터 조회 실패: {username}, {str(e)}")
                    # 데이터 조회 실패는 인증 실패를 의미할 수 있음
                    if "인증" in str(e) or "로그인" in str(e) or "권한" in str(e):
                        return False, "로그인 실패: 인증 정보가 올바르지 않습니다"
                    else:
                        return False, f"로그인 실패: {str(e)}"
            else:
                logger.warning(f"롯데 계정 검증 실패: {username}")
                return False, "로그인 실패: 인증 정보가 올바르지 않습니다"
                
        except ImportError as e:
            logger.error(f"AUTOLOTTE 모듈 import 실패: {e}")
            return False, "시스템 오류: 롯데 검증 모듈을 찾을 수 없습니다"
        except Exception as e:
            logger.error(f"롯데 계정 검증 예외: {username}, {str(e)}")
            return False, f"검증 중 오류 발생: {str(e)}"
    
    def _build_login_payload(self, user_id: str, password: str, l_visitor: str, gv_statustime: str) -> str:
        """로그인 XML 페이로드 구성 (AUTOLOTTE와 동일한 Nexacro Dataset 형식)"""
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<Root xmlns="http://www.nexacroplatform.com/platform/dataset">
  <Parameters>
    <Parameter id="l_visitor">{l_visitor}</Parameter>
    <Parameter id="gv_statustime">{gv_statustime}</Parameter>
  </Parameters>
  <Dataset id="dsLogin">
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

class ShillaAccountValidator:
    """신라 면세점 계정 검증 클래스"""
    
    def __init__(self, dev_mode: bool = False):
        self.login_url = "https://www.shillasrm.com/login.do"
        self.dev_mode = dev_mode
        
    async def validate_account(self, username: str, password: str) -> Tuple[bool, str]:
        """신라 계정 유효성 검증 (Playwright 사용)"""
        try:
            logger.info(f"신라 계정 검증 시작: {username}")
            
            # 개발 모드에서는 더미 응답 반환
            if self.dev_mode:
                logger.info(f"개발 모드: 신라 계정 {username} 검증 스킵")
                # 테스트 계정들에 대해서는 성공 응답
                if username in ["G000056324", "test456", "admin"]:
                    return True, "개발 모드: 계정 검증 성공"
                else:
                    return False, "개발 모드: 잘못된 테스트 계정"
            
            async with async_playwright() as p:
                # 브라우저 실행 (headless 모드)
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )
                
                try:
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                    )
                    page = await context.new_page()
                    
                    # 로그인 페이지 접근
                    await page.goto(self.login_url, timeout=15000)
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    
                    # 면세업무 라디오 버튼 선택
                    duty_free_radio = await page.query_selector('input[name="pro_cls"][value="2"]')
                    if duty_free_radio:
                        await duty_free_radio.check()
                        logger.info("면세업무 라디오 버튼 선택")
                    
                    # 사용자명 입력
                    username_field = await page.query_selector('input[name="username"]')
                    if not username_field:
                        return False, "사용자명 입력 필드를 찾을 수 없습니다"
                    
                    await username_field.fill(username)
                    logger.info(f"사용자명 입력: {username}")
                    
                    # 비밀번호 입력
                    password_field = await page.query_selector('input[name="password"]')
                    if not password_field:
                        return False, "비밀번호 입력 필드를 찾을 수 없습니다"
                    
                    await password_field.fill(password)
                    logger.info("비밀번호 입력 완료")
                    
                    # 회사 선택 (기본값: 호텔신라)
                    company_select = await page.query_selector('#comp')
                    if company_select:
                        await company_select.select_option(value="Y1D0")
                        logger.info("회사 선택: 호텔신라")
                    
                    # 숨겨진 필드들 설정
                    await page.evaluate('''
                        document.getElementById("company").value = "Y1D0";
                        document.getElementById("type").value = "2";
                        document.getElementById("lang").value = "ko";
                    ''')
                    
                    # 로그인 실행 (JavaScript 함수 호출 또는 버튼 클릭)
                    try:
                        # 먼저 JavaScript login() 함수 실행 시도
                        await page.evaluate('login()')
                        logger.info("JavaScript login() 함수 실행")
                    except:
                        # JavaScript 함수가 없다면 버튼 클릭 시도
                        login_button_selector = 'button[type="submit"], input[type="submit"], .login-btn, #loginBtn, [onclick*="login"]'
                        login_button = await page.query_selector(login_button_selector)
                        if not login_button:
                            return False, "로그인 버튼을 찾을 수 없습니다"
                        
                        await login_button.click()
                        logger.info("로그인 버튼 클릭")
                    
                    # 로그인 결과 대기 및 확인
                    await page.wait_for_timeout(3000)  # 3초 대기
                    
                    current_url = page.url
                    logger.info(f"로그인 후 현재 URL: {current_url}")
                    
                    # 페이지 내용 확인 (디버깅용)
                    page_title = await page.title()
                    logger.info(f"페이지 제목: {page_title}")
                    
                    # iframe 기반 로그인인지 확인
                    iframe = await page.query_selector('iframe[name="i_login_page"]')
                    if iframe:
                        iframe_content = await iframe.content_frame()
                        if iframe_content:
                            iframe_url = iframe_content.url
                            logger.info(f"iframe URL: {iframe_url}")
                            
                            # iframe 내용에서 성공/실패 확인
                            iframe_text = await iframe_content.text_content('body')
                            logger.info(f"iframe 내용: {iframe_text[:200]}...")
                            
                            if "성공" in iframe_text or "main" in iframe_url or "dashboard" in iframe_url:
                                logger.info(f"신라 계정 검증 성공: {username}")
                                return True, "로그인 성공"
                    
                    # 메인 페이지에서 성공 확인
                    if current_url != self.login_url and "login" not in current_url.lower():
                        logger.info(f"신라 계정 검증 성공 (URL 변경): {username}")
                        return True, "로그인 성공"
                    
                    # 성공 키워드 확인
                    page_content = await page.text_content('body')
                    success_keywords = ["로그아웃", "마이페이지", "메인", "대시보드", "환영"]
                    for keyword in success_keywords:
                        if keyword in page_content:
                            logger.info(f"신라 계정 검증 성공 (키워드 발견): {username}")
                            return True, "로그인 성공"
                    
                    # 실패 메시지 확인
                    error_keywords = ["로그인 실패", "인증 실패", "아이디", "비밀번호", "확인"]
                    for keyword in error_keywords:
                        if keyword in page_content:
                            logger.info(f"로그인 실패 키워드 발견: {keyword}")
                            return False, f"로그인 실패: {keyword} 관련 오류"
                    
                    logger.info("로그인 결과를 명확히 판별할 수 없음")
                    return False, "로그인 실패: 인증 정보가 올바르지 않습니다"
                
                finally:
                    await browser.close()
                    
        except Exception as e:
            logger.error(f"신라 계정 검증 예외: {username}, {str(e)}")
            return False, f"검증 중 오류 발생: {str(e)}"

class AccountVerificationService:
    """통합 계정 검증 서비스"""
    
    def __init__(self, dev_mode: bool = True):  # 개발 모드를 기본값으로 설정
        self.lotte_validator = LotteAccountValidator(dev_mode=dev_mode)
        self.shilla_validator = ShillaAccountValidator(dev_mode=dev_mode)
    
    async def verify_account(self, duty_free_type: str, username: str, password: str) -> Dict[str, any]:
        """계정 검증 실행"""
        try:
            if duty_free_type == "lotte":
                success, message = self.lotte_validator.validate_account(username, password)
            elif duty_free_type == "shilla":
                success, message = await self.shilla_validator.validate_account(username, password)
            else:
                return {
                    "success": False,
                    "message": "지원하지 않는 면세점 타입입니다",
                    "duty_free_type": duty_free_type
                }
            
            return {
                "success": success,
                "message": message,
                "duty_free_type": duty_free_type,
                "username": username
            }
            
        except Exception as e:
            logger.error(f"계정 검증 서비스 오류: {duty_free_type}, {username}, {str(e)}")
            return {
                "success": False,
                "message": f"검증 서비스 오류: {str(e)}",
                "duty_free_type": duty_free_type
            }

# 전역 서비스 인스턴스
verification_service = AccountVerificationService(dev_mode=False)