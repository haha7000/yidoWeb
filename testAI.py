import openai
from PIL import Image
import base64
import io
from dotenv import load_dotenv
import os

load_dotenv()

# 🔑 OpenAI API 키 설정
openai.api_key = os.getenv("OPENAI_API_KEY_COMPANY")  # 보통은 환경 변수로 관리합니다!

# 🖼 이미지 로딩 및 base64 인코딩
def encode_image(image_path):
    with Image.open(image_path) as img:
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()

# 이미지 경로
image_path = "/Users/gimdonghun/Downloads/test.png"  # 경로 수정!

# base64 인코딩
base64_image = encode_image(image_path)

# 🔍 GPT-4-Vision API 호출
response = openai.chat.completions.create(
    model="gpt-4.1",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "이 이미지를 분석해서 주요 내용을 설명해줘."},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}"
                    },
                },
            ],
        }
    ],
    max_tokens=1000
)

# 결과 출력
print(response.choices[0].message.content)