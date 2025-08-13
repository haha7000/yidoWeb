import asyncio
import aiohttp
import os
from playwright.async_api import async_playwright

async def upload_shilla_excel(excel_file_path):
    """신라 엑셀 파일을 업로드 API로 전송"""
    try:
        print(f"📤 신라 엑셀 업로드 시작: {excel_file_path}")
        
        # 파일 존재 확인
        if not os.path.exists(excel_file_path):
            print(f"❌ 파일이 존재하지 않습니다: {excel_file_path}")
            return
        
        # 업로드 API 설정
        # EC2의 공인 IP를 여기에 입력하세요
        ec2_ip = "18.142.243.40"  # EC2 공인 IP
        api_url = f"http://{ec2_ip}:8001/upload-excel/"
        
        # 로그인 토큰 설정 (실제 토큰으로 변경 필요)
        # 여기서는 세션 쿠키 방식으로 진행
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
            # 먼저 로그인 (실제 credentials로 변경 필요)
            login_data = {
                "username": "haha",  # 실제 사용자명으로 변경
                "password": "haha"  # 실제 비밀번호로 변경
            }
            
            print("🔐 웹사이트 로그인 시도...")
            async with session.post(f"http://{ec2_ip}:8001/login/", data=login_data, allow_redirects=False) as login_resp:
                # 로그인 성공시 302 리다이렉트가 옴
                if login_resp.status in [200, 302]:
                    print("✅ 로그인 성공!")
                    
                    # 쿠키에서 access_token 확인
                    cookies = session.cookie_jar.filter_cookies(f"http://{ec2_ip}:8001")
                    if 'access_token' in [cookie.key for cookie in cookies.values()]:
                        print("✅ JWT 토큰 획득 성공!")
                    else:
                        print("⚠️ JWT 토큰이 없지만 계속 진행...")
                else:
                    print(f"❌ 로그인 실패: {login_resp.status}")
                    error_text = await login_resp.text()
                    print(f"로그인 오류: {error_text}")
                    return
            
            # 엑셀 파일 업로드
            print("📤 엑셀 파일 업로드 중...")
            with open(excel_file_path, 'rb') as f:
                form_data = aiohttp.FormData()
                form_data.add_field('excel_file', f, filename='shilla_report.xlsx')
                form_data.add_field('duty_free_type', 'shilla')
                
                async with session.post(api_url, data=form_data) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        print("✅ 신라 엑셀 업로드 성공!")
                        print(f"📊 업로드 결과: {result}")
                        
                        # 업로드 완료 후 파일 삭제 (선택사항)
                        # os.remove(excel_file_path) 
                        print("🗑️ 임시 파일 삭제 완료")
                        
                    else:
                        error_text = await resp.text()
                        print(f"❌ 신라 엑셀 업로드 실패: {resp.status}")
                        print(f"오류 내용: {error_text}")
                        
    except Exception as e:
        print(f"❌ 신라 엑셀 업로드 중 오류 발생: {e}")

async def main():
    cookies = None  # 로그인 후 쿠키 저장용 변수
    
    # 프로젝트 내부 downloads 폴더 생성
    downloads_dir = os.path.join(os.path.dirname(__file__), 'downloads')
    os.makedirs(downloads_dir, exist_ok=True)
    
    # 다운로드 파일 경로 설정
    download_path = os.path.join(downloads_dir, 'shilla_report.xlsx')
    
    async with async_playwright() as p:
        # 브라우저 실행 (백그라운드에서 실행되도록 headless=True 설정)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()

        # 로그인 페이지 접속
        await page.goto("https://www.shillasrm.com/login.do")
        # 로그인 입력창이 나타날 때까지 대기
        await page.wait_for_selector("#username", timeout=10000)

        # 아이디 입력
        await page.fill("#username", "G000056324")

        # 비밀번호 입력
        await page.fill("#idbox", "19850327ng@!!")

        # 로그인 버튼 클릭
        await page.click("#wrap > div > form > div > div.background_img > div > div.box_login")

        # 로그인 후 팝업창 닫기 (x 버튼 클릭 robust version)
        try:
            popup_close_btn = page.locator('xpath=/html/body/sc-window/sc-toolbar/sc-button[3]')
            await popup_close_btn.wait_for(timeout=10000)
            if await popup_close_btn.is_visible():
                await popup_close_btn.click()
                print("팝업창 닫기 성공!")
                # 로그인 후 쿠키 저장
                cookies = await context.cookies()
                print("쿠키 저장 완료!")
            else:
                print("팝업창이 안 보입니다.")
                # 추가 버튼 클릭

        except Exception as e:
            print(f"팝업창 닫기에 실패했어요. 오류: {e}")
        try:
            await page.click('xpath=/html/body/sc-mdi/div/div[1]/div[2]/div[2]/sc-mdi-topmenu/div[1]/ul/li[2]')
            print("추가 버튼 클릭 완료!")
        except Exception as e:
            print(f"추가 버튼 클릭 실패: {e}")

        # 매출조회 버튼 클릭
        try:
            await page.click('xpath=/html/body/sc-mdi/div/div[2]/div[1]/div[2]/sc-mdi-leftmenu/div/ul/li[4]/a')
            print("매출조회 버튼 클릭 완료!")
        except Exception as e:
            print(f"매출조회 버튼 클릭 실패: {e}")

        # 입력창에 전날 날짜 자동 입력
        # 어제 날짜 계산
        from datetime import datetime, timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        # 시작일 입력 (evaluate 방식)
        await page.wait_for_selector('xpath=/html/body/sc-mdi/div/div[2]/div[3]/sc-mdi-content/div/iron-pages/sc-mdi-window[2]/div/em-guide-sale/div/es-guide-sale-list/cc-toggle-container/div/div[1]/table/tbody/tr[1]/td[1]/cc-from-to-date/sc-date-field[1]//input', timeout=10000)
        try:
            await page.evaluate(f"""
                () => {{
                    document.evaluate(
                        "/html/body/sc-mdi/div/div[2]/div[3]/sc-mdi-content/div/iron-pages/sc-mdi-window[2]/div/em-guide-sale/div/es-guide-sale-list/cc-toggle-container/div/div[1]/table/tbody/tr[1]/td[1]/cc-from-to-date/sc-date-field[1]//input",
                        document,
                        null,
                        XPathResult.FIRST_ORDERED_NODE_TYPE,
                        null
                    ).singleNodeValue.value = "{yesterday}";
                }}
            """)
            print("시작일 입력 완료!")
        except Exception as e:
            print(f"시작일 입력 실패: {e}")

        # 종료일 입력 (evaluate 방식)
        await page.wait_for_selector('xpath=/html/body/sc-mdi/div/div[2]/div[3]/sc-mdi-content/div/iron-pages/sc-mdi-window[2]/div/em-guide-sale/div/es-guide-sale-list/cc-toggle-container/div/div[1]/table/tbody/tr[1]/td[1]/cc-from-to-date/sc-date-field[2]//input', timeout=10000)
        try:
            await page.evaluate(f"""
                () => {{
                    document.evaluate(
                        "/html/body/sc-mdi/div/div[2]/div[3]/sc-mdi-content/div/iron-pages/sc-mdi-window[2]/div/em-guide-sale/div/es-guide-sale-list/cc-toggle-container/div/div[1]/table/tbody/tr[1]/td[1]/cc-from-to-date/sc-date-field[2]//input",
                        document,
                        null,
                        XPathResult.FIRST_ORDERED_NODE_TYPE,
                        null
                    ).singleNodeValue.value = "{yesterday}";
                }}
            """)
            print("종료일 입력 완료!")
        except Exception as e:
            print(f"종료일 입력 실패: {e}")

        # 조회 버튼 클릭
        try:
            await page.click('xpath=/html/body/sc-mdi/div/div[2]/div[3]/sc-mdi-content/div/iron-pages/sc-mdi-window[2]/div/em-guide-sale/div/es-guide-sale-list/sc-toolbar/sc-button[1]')
            print("조회 버튼 클릭 완료!")
        except Exception as e:
            print(f"조회 버튼 클릭 실패: {e}")

        # 조회 후 35초 대기 후 다운로드 버튼 클릭
        try:
            print("조회 결과 로딩 대기 중... (35초)")
            await page.wait_for_timeout(35000)

            # 다운로드 이벤트 핸들러 등록
            async def on_download(download):
                await download.save_as(download_path)
                print("✅ 엑셀 다운로드 완료!")
                
                # 다운로드 완료 후 신라 엑셀 업로드 API 호출
                #await upload_shilla_excel(download_path)

            page.on("download", on_download)

            # 다운로드 버튼 클릭 (재시도 로직 포함)
            max_retries = 3
            download_button_xpath = 'xpath=/html/body/sc-mdi/div/div[2]/div[3]/sc-mdi-content/div/iron-pages/sc-mdi-window[2]/div/em-guide-sale/div/es-guide-sale-list/sc-toolbar/sc-button[2]'
            
            for attempt in range(max_retries):
                try:
                    print(f"다운로드 버튼 클릭 시도 {attempt + 1}/{max_retries}")
                    await page.click(download_button_xpath)
                    print("✅ 다운로드 버튼 클릭 성공!")
                    break
                except Exception as click_error:
                    print(f"다운로드 버튼 클릭 실패 (시도 {attempt + 1}): {click_error}")
                    
                    if attempt < max_retries - 1:
                        print("2초 대기 후 재시도...")
                        await page.wait_for_timeout(2000)
                        
                        # 팝업이나 다른 요소가 방해하는 경우를 위한 추가 처리
                        try:
                            # 일반적인 팝업 요소들 확인 및 닫기
                            popup_selectors = [
                                'button:has-text("확인")',
                                'button:has-text("OK")', 
                                'button:has-text("닫기")',
                                'button:has-text("취소")',
                                '[class*="popup"] button',
                                '[class*="modal"] button',
                                '[class*="dialog"] button',
                                '.ui-dialog-titlebar-close',
                                '[data-dismiss="modal"]'
                            ]
                            
                            for selector in popup_selectors:
                                try:
                                    popup_element = await page.query_selector(selector)
                                    if popup_element:
                                        await popup_element.click()
                                        print(f"팝업 닫기 성공: {selector}")
                                        await page.wait_for_timeout(500)
                                        break
                                except:
                                    continue
                            
                            # ESC 키로 팝업 닫기 시도
                            await page.keyboard.press('Escape')
                            print("ESC 키로 팝업 닫기 시도")
                            await page.wait_for_timeout(1000)
                            
                        except Exception as popup_error:
                            print(f"팝업 처리 중 오류: {popup_error}")
                            pass
                        
                        # 페이지 새로고침이나 다른 방해 요소 제거 시도
                        try:
                            # 다운로드 버튼이 다시 보이는지 확인
                            await page.wait_for_selector(download_button_xpath.replace('xpath=', ''), timeout=5000)
                            print("다운로드 버튼 재확인 완료")
                        except:
                            print("다운로드 버튼 재확인 실패, 계속 진행")
                    else:
                        print("❌ 모든 다운로드 버튼 클릭 시도 실패")
                        raise Exception("다운로드 버튼 클릭 최종 실패")

        except Exception as e:
            print(f"엑셀 다운로드 버튼 클릭 최종 실패: {e}")

        # 다운로드 완료까지 대기
        print("다운로드 및 업로드 완료 대기 중... (최대 60초)")
        await page.wait_for_timeout(60000)  # 60초 대기
        
        print("✅ 작업 완료! 브라우저를 종료합니다.")
        await browser.close()

# 실행 (스크립트로 직접 실행될 때만)
if __name__ == "__main__":
    asyncio.run(main())
