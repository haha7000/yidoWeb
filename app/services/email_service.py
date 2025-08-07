"""
이메일 발송 서비스
"""
import smtplib
import secrets
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

class EmailService:
    def __init__(self):
        # Gmail SMTP 설정 (환경변수에서 읽기)
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.smtp_username = os.getenv("SMTP_USERNAME", "ghehdch13@gmail.com")  # 임시 계정
        self.smtp_password = os.getenv("SMTP_PASSWORD", "ibhznjbtdprghrvt")  # 임시 앱 비밀번호
        self.from_email = self.smtp_username
        self.admin_email = os.getenv("ADMIN_EMAIL", "ghehdch13@gmail.com")  # 관리자 이메일
    
    def _get_base_url(self) -> str:
        """기본 URL 반환 - 환경에 따라 동적으로 설정"""
        # 환경변수에서 BASE_URL을 가져오고, 없으면 프로덕션 도메인 사용
        base_url = os.getenv('BASE_URL')
        if base_url:
            return base_url.rstrip('/')  # 끝의 슬래시 제거
        # 프로덕션 환경 기본값
        return "https://yido.ydb2c.com"
    
    def generate_random_password(self, length: int = 12) -> str:
        """랜덤 비밀번호 생성"""
        # 대소문자, 숫자, 특수문자 조합
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        
        # 각 카테고리에서 최소 1개씩 포함
        password = [
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.digits),
            secrets.choice("!@#$%^&*")
        ]
        
        # 나머지 길이만큼 랜덤 문자 추가
        for _ in range(length - 4):
            password.append(secrets.choice(characters))
        
        # 섞기
        secrets.SystemRandom().shuffle(password)
        return ''.join(password)
    
    def send_email(self, to_email: str, subject: str, html_body: str, text_body: Optional[str] = None) -> bool:
        """이메일 발송"""
        try:
            # 디버그 정보
            print(f"🐛 DEBUG - SMTP 설정:")
            print(f"   Username: {self.smtp_username}")
            print(f"   From Email: {self.from_email}")
            print(f"   To Email: {to_email}")
            
            # 메시지 생성
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # 텍스트 버전 (HTML에서 태그 제거한 버전)
            if not text_body:
                import re
                text_body = re.sub('<[^<]+?>', '', html_body)
            
            # 텍스트와 HTML 부분 추가
            part1 = MIMEText(text_body, 'plain', 'utf-8')
            part2 = MIMEText(html_body, 'html', 'utf-8')
            
            msg.attach(part1)
            msg.attach(part2)
            
            # SMTP 서버 연결 및 발송
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            print(f"✅ 이메일 발송 성공: {to_email}")
            return True
            
        except Exception as e:
            print(f"❌ 이메일 발송 실패: {to_email} - {str(e)}")
            return False
    
    def send_password_email(self, user_email: str, username: str, password: str, company_name: str) -> bool:
        """비밀번호 발송 이메일"""
        subject = "[YIDOWEB] 계정 승인 완료 - 로그인 정보 안내"
        
        base_url = self._get_base_url()
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }}
                .content {{
                    padding: 40px 30px;
                }}
                .password-box {{
                    background-color: #f8fafc;
                    border: 2px solid #e2e8f0;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 20px 0;
                    text-align: center;
                }}
                .password {{
                    font-family: 'Courier New', monospace;
                    font-size: 24px;
                    font-weight: bold;
                    color: #1e40af;
                    letter-spacing: 2px;
                }}
                .info-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                .info-table td {{
                    padding: 10px;
                    border-bottom: 1px solid #e2e8f0;
                }}
                .info-table td:first-child {{
                    font-weight: bold;
                    color: #374151;
                    width: 30%;
                }}
                .button {{
                    display: inline-block;
                    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                    color: white;
                    padding: 15px 30px;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: bold;
                    margin: 20px 0;
                }}
                .footer {{
                    background-color: #f8fafc;
                    padding: 20px;
                    text-align: center;
                    color: #6b7280;
                    font-size: 14px;
                }}
                .warning {{
                    background-color: #fef3c7;
                    border-left: 4px solid #f59e0b;
                    padding: 15px;
                    margin: 20px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 계정 승인 완료!</h1>
                    <p>YIDOWEB 시스템 사용이 승인되었습니다.</p>
                </div>
                
                <div class="content">
                    <p>안녕하세요, <strong>{company_name}</strong>의 <strong>{username}</strong>님!</p>
                    <p>귀하의 계정 가입 신청이 승인되어 로그인 정보를 안내드립니다.</p>
                    
                    <table class="info-table">
                        <tr>
                            <td>아이디</td>
                            <td><strong>{username}</strong></td>
                        </tr>
                        <tr>
                            <td>회사명</td>
                            <td>{company_name}</td>
                        </tr>
                        <tr>
                            <td>승인일시</td>
                            <td>{datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}</td>
                        </tr>
                    </table>
                    
                    <div class="password-box">
                        <p style="margin-bottom: 10px;"><strong>임시 비밀번호</strong></p>
                        <div class="password">{password}</div>
                    </div>
                    
                    <div class="warning">
                        <strong>⚠️ 보안 안내</strong><br>
                        • 이 비밀번호는 임시로 발급된 것입니다.<br>
                        • 로그인 후 원하시면 비밀번호를 변경하실 수 있습니다.<br>
                        • 이 이메일은 안전한 곳에 보관해 주세요.
                    </div>
                    
                    <div style="text-align: center;">
                        <a href="{base_url}/login/" class="button">
                            🔓 지금 로그인하기
                        </a>
                    </div>
                    
                    <p style="margin-top: 40px;">
                        문의사항이 있으시면 관리자에게 연락해 주세요.<br>
                        감사합니다.
                    </p>
                </div>
                
                <div class="footer">
                    <p>본 메일은 발신 전용입니다. 문의사항은 관리자에게 연락해 주세요.</p>
                    <p>© 2025 YIDOWEB. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(user_email, subject, html_body)
    
    def send_new_registration_notification(self, username: str, email: str, company_name: str, position: str) -> bool:
        """관리자에게 신규 가입 알림 발송"""
        subject = "[YIDOWEB] 🔔 신규 가입 신청 알림"
        
        base_url = self._get_base_url()
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }}
                .content {{
                    padding: 40px 30px;
                }}
                .applicant-info {{
                    background-color: #f8fafc;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 20px 0;
                }}
                .info-table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                .info-table td {{
                    padding: 12px;
                    border-bottom: 1px solid #e2e8f0;
                }}
                .info-table td:first-child {{
                    font-weight: bold;
                    color: #374151;
                    width: 30%;
                }}
                .button {{
                    display: inline-block;
                    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                    color: white;
                    padding: 15px 30px;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: bold;
                    margin: 10px;
                }}
                .button.approve {{
                    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                }}
                .button.reject {{
                    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                }}
                .footer {{
                    background-color: #f8fafc;
                    padding: 20px;
                    text-align: center;
                    color: #6b7280;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔔 신규 가입 신청</h1>
                    <p>새로운 사용자가 가입을 신청했습니다.</p>
                </div>
                
                <div class="content">
                    <p>안녕하세요, 관리자님!</p>
                    <p>다음과 같은 신규 가입 신청이 접수되었습니다.</p>
                    
                    <div class="applicant-info">
                        <h3 style="margin-top: 0; color: #1f2937;">👤 신청자 정보</h3>
                        <table class="info-table">
                            <tr>
                                <td>아이디</td>
                                <td><strong>{username}</strong></td>
                            </tr>
                            <tr>
                                <td>이메일</td>
                                <td>{email}</td>
                            </tr>
                            <tr>
                                <td>회사명</td>
                                <td><strong>{company_name}</strong></td>
                            </tr>
                            <tr>
                                <td>직책</td>
                                <td>{position}</td>
                            </tr>
                            <tr>
                                <td>신청일시</td>
                                <td>{datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}</td>
                            </tr>
                        </table>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <p><strong>관리자 페이지에서 승인 또는 거절 처리를 해주세요.</strong></p>
                        <a href="{base_url}/admin/login" class="button">
                            🔧 관리자 페이지로 이동
                        </a>
                    </div>
                    
                    <div style="background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0;">
                        <strong>📋 처리 안내</strong><br>
                        • 관리자 페이지 → 신규신청 탭에서 확인 가능<br>
                        • 승인 시 신청자에게 자동으로 비밀번호가 발송됩니다<br>
                        • 거절 시 해당 계정은 재가입이 불가합니다
                    </div>
                </div>
                
                <div class="footer">
                    <p>이 알림은 시스템에서 자동으로 발송되었습니다.</p>
                    <p>© 2025 YIDOWEB Admin System. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(self.admin_email, subject, html_body)
    
    def send_rejection_notification(self, user_email: str, username: str, company_name: str) -> bool:
        """가입 거절 알림 이메일"""
        subject = "[YIDOWEB] 가입 신청 결과 안내"
        
        base_url = self._get_base_url()
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }}
                .content {{
                    padding: 40px 30px;
                    text-align: center;
                }}
                .footer {{
                    background-color: #f8fafc;
                    padding: 20px;
                    text-align: center;
                    color: #6b7280;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📋 가입 신청 결과</h1>
                </div>
                
                <div class="content">
                    <p>안녕하세요, <strong>{company_name}</strong>의 <strong>{username}</strong>님!</p>
                    <p>귀하의 YIDOWEB 가입 신청을 검토한 결과,<br>
                    아쉽게도 현재 가입 승인이 어려운 상황입니다.</p>
                    
                    <div style="background-color: #fef2f2; border: 2px solid #fecaca; border-radius: 8px; padding: 20px; margin: 30px 0;">
                        <h3 style="color: #dc2626; margin-top: 0;">❌ 가입 승인 불가</h3>
                        <p>관리자 검토 결과 가입 요건을 충족하지 않아<br>
                        가입을 승인하지 못하게 되었습니다.</p>
                    </div>
                    
                    <p>문의사항이 있으시면 관리자에게 별도로 연락해 주시기 바랍니다.</p>
                    <p>감사합니다.</p>
                </div>
                
                <div class="footer">
                    <p>본 메일은 발신 전용입니다. 문의사항은 관리자에게 연락해 주세요.</p>
                    <p>© 2025 YIDOWEB. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(user_email, subject, html_body)
    
    def send_username_recovery_email(self, user_email: str, username: str, company_name: str) -> bool:
        """아이디 찾기 결과 이메일"""
        subject = "[YIDOWEB] 아이디 찾기 결과"
        
        base_url = self._get_base_url()
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }}
                .content {{
                    padding: 40px 30px;
                }}
                .username-box {{
                    background-color: #f8fafc;
                    border: 2px solid #e2e8f0;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 20px 0;
                    text-align: center;
                }}
                .username {{
                    font-family: 'Courier New', monospace;
                    font-size: 24px;
                    font-weight: bold;
                    color: #1e40af;
                    letter-spacing: 1px;
                }}
                .info-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                .info-table td {{
                    padding: 10px;
                    border-bottom: 1px solid #e2e8f0;
                }}
                .info-table td:first-child {{
                    font-weight: bold;
                    color: #374151;
                    width: 30%;
                }}
                .button {{
                    display: inline-block;
                    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                    color: white;
                    padding: 15px 30px;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: bold;
                    margin: 20px 0;
                }}
                .footer {{
                    background-color: #f8fafc;
                    padding: 20px;
                    text-align: center;
                    color: #6b7280;
                    font-size: 14px;
                }}
                .warning {{
                    background-color: #fef3c7;
                    border-left: 4px solid #f59e0b;
                    padding: 15px;
                    margin: 20px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔍 아이디 찾기 결과</h1>
                    <p>요청하신 아이디 정보를 안내드립니다.</p>
                </div>
                
                <div class="content">
                    <p>안녕하세요, <strong>{company_name}</strong> 소속 회원님!</p>
                    <p>해당 이메일로 등록된 아이디 정보입니다.</p>
                    
                    <table class="info-table">
                        <tr>
                            <td>회사명</td>
                            <td>{company_name}</td>
                        </tr>
                        <tr>
                            <td>이메일</td>
                            <td>{user_email}</td>
                        </tr>
                        <tr>
                            <td>조회일시</td>
                            <td>{datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}</td>
                        </tr>
                    </table>
                    
                    <div class="username-box">
                        <p style="margin-bottom: 10px;"><strong>찾으신 아이디</strong></p>
                        <div class="username">{username}</div>
                    </div>
                    
                    <div class="warning">
                        <strong>🔒 보안 안내</strong><br>
                        • 본인이 요청한 것이 아니라면 즉시 관리자에게 연락해 주세요.<br>
                        • 아이디와 비밀번호는 안전한 곳에 보관해 주세요.<br>
                        • 정기적으로 비밀번호를 변경하시기 바랍니다.
                    </div>
                    
                    <div style="text-align: center;">
                        <a href="{base_url}/login/" class="button">
                            🔓 로그인하러 가기
                        </a>
                    </div>
                    
                    <p style="margin-top: 40px;">
                        비밀번호를 잊으셨다면 로그인 페이지에서 "비밀번호 찾기"를 이용해 주세요.<br>
                        감사합니다.
                    </p>
                </div>
                
                <div class="footer">
                    <p>본 메일은 발신 전용입니다. 문의사항은 관리자에게 연락해 주세요.</p>
                    <p>© 2025 YIDOWEB. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(user_email, subject, html_body)
    
    def send_password_reset_email(self, user_email: str, username: str, company_name: str, reset_token: str) -> bool:
        """비밀번호 재설정 링크 이메일"""
        subject = "[YIDOWEB] 비밀번호 재설정 요청"
        
        base_url = self._get_base_url()
        reset_url = f"{base_url}/auth/reset-password?token={reset_token}"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }}
                .content {{
                    padding: 40px 30px;
                }}
                .info-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                .info-table td {{
                    padding: 10px;
                    border-bottom: 1px solid #e2e8f0;
                }}
                .info-table td:first-child {{
                    font-weight: bold;
                    color: #374151;
                    width: 30%;
                }}
                .button {{
                    display: inline-block;
                    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                    color: white;
                    padding: 15px 30px;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: bold;
                    margin: 20px 0;
                    font-size: 16px;
                }}
                .footer {{
                    background-color: #f8fafc;
                    padding: 20px;
                    text-align: center;
                    color: #6b7280;
                    font-size: 14px;
                }}
                .warning {{
                    background-color: #fef2f2;
                    border-left: 4px solid #ef4444;
                    padding: 15px;
                    margin: 20px 0;
                }}
                .info-box {{
                    background-color: #eff6ff;
                    border-left: 4px solid #3b82f6;
                    padding: 15px;
                    margin: 20px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔑 비밀번호 재설정</h1>
                    <p>비밀번호 재설정 요청을 받았습니다.</p>
                </div>
                
                <div class="content">
                    <p>안녕하세요, <strong>{company_name}</strong>의 <strong>{username}</strong>님!</p>
                    <p>귀하의 계정에 대한 비밀번호 재설정 요청이 접수되었습니다.</p>
                    
                    <table class="info-table">
                        <tr>
                            <td>아이디</td>
                            <td><strong>{username}</strong></td>
                        </tr>
                        <tr>
                            <td>이메일</td>
                            <td>{user_email}</td>
                        </tr>
                        <tr>
                            <td>요청일시</td>
                            <td>{datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}</td>
                        </tr>
                    </table>
                    
                    <div class="info-box">
                        <strong>📋 재설정 방법</strong><br>
                        아래 버튼을 클릭하여 새로운 비밀번호를 설정해 주세요.<br>
                        링크는 <strong>1시간 동안</strong>만 유효합니다.
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_url}" class="button">
                            🔑 비밀번호 재설정하기
                        </a>
                    </div>
                    
                    <div class="warning">
                        <strong>⚠️ 보안 경고</strong><br>
                        • 본인이 요청한 것이 아니라면 이 이메일을 무시하고 관리자에게 연락해 주세요.<br>
                        • 링크를 클릭하기 전에 URL이 올바른지 확인해 주세요.<br>
                        • 비밀번호 재설정 후에는 이 링크는 더 이상 사용할 수 없습니다.
                    </div>
                    
                    <p style="margin-top: 40px; font-size: 14px; color: #6b7280;">
                        링크가 작동하지 않는다면 아래 URL을 복사해서 브라우저에 직접 입력하세요:<br>
                        <code>{reset_url}</code>
                    </p>
                </div>
                
                <div class="footer">
                    <p>본 메일은 발신 전용입니다. 문의사항은 관리자에게 연락해 주세요.</p>
                    <p>© 2025 YIDOWEB. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(user_email, subject, html_body)

# 전역 인스턴스
email_service = EmailService()