import openai
import os
from dotenv import load_dotenv
from app.core.config import settings

load_dotenv()

def ShillaClassificationUseGpt(ocr_text: str) -> str:
    # 설정에서 프롬프트 파일 경로 가져오기
    prompt_path = settings.shilla_prompt_path
    
    SYSTEM_PROMPT = open(prompt_path, "r").read()
    openai.api_key = os.getenv("OPENAI_API_KEY_COMPANY") 
    response = openai.ChatCompletion.create(
        model="gpt-4.1-mini",
        messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": ocr_text}
        ],
        temperature=0.0
    )
    return response['choices'][0]['message']['content']