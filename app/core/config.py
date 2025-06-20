import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """애플리케이션 설정"""
    
    def __init__(self):
        # 프로젝트 루트 경로 설정
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.app_dir = os.path.dirname(self.current_dir)
        self.project_root = os.path.dirname(self.app_dir)
        
        # 디렉토리 경로들
        self.static_dir = os.getenv("STATIC_DIR", os.path.join(self.project_root, "static"))
        self.uploads_dir = os.getenv("UPLOADS_DIR", os.path.join(self.project_root, "uploads"))
        self.templates_dir = os.getenv("TEMPLATES_DIR", os.path.join(self.project_root, "templates"))
        self.translations_dir = os.getenv("TRANSLATIONS_DIR", os.path.join(self.project_root, "translations"))
        self.excel_template_dir = os.getenv("EXCEL_TEMPLATE_DIR", os.path.join(self.project_root, "excel_template"))
        
        # 프롬프트 파일 경로들
        self.lotte_prompt_path = os.getenv("LOTTE_PROMPT_PATH", os.path.join(self.project_root, "LottePrompt.txt"))
        self.shilla_prompt_path = os.getenv("SHILLA_PROMPT_PATH", os.path.join(self.project_root, "ShillaPrompt.txt"))
        
        # 필요한 디렉토리들 생성
        os.makedirs(self.uploads_dir, exist_ok=True)
        os.makedirs(self.excel_template_dir, exist_ok=True)
    
    def get_user_uploads_dir(self, user_id: int) -> str:
        """사용자별 업로드 디렉토리 경로 반환"""
        user_dir = os.path.join(self.uploads_dir, f"user_{user_id}")
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

# 전역 설정 인스턴스
settings = Settings() 