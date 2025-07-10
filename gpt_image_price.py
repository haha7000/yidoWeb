import openai
import base64

openai.api_key = "api키를 입력해주세요" 

# 환율 (2025년 7월 기준 1 USD ≈ 1,374 KRW)
usd_to_krw = 1374  

input_token_price_usd = 0.0025  # $2.50 / 1M = $0.0025 per 1K 입력토큰 가격
output_token_price_usd = 0.01   # $10 / 1M = $0.01 per 1K 출력토큰 가격

image_path = "여기에 이미지 경로 입력해주세요" # 예시 : /Users/gimdonghun/Downloads/k_test.jpg
with open(image_path, "rb") as image_file:
    base64_image = base64.b64encode(image_file.read()).decode("utf-8")

response = openai.ChatCompletion.create(
    model="gpt-4o", # 모델 변경 가능
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "이 이미지에 뭐가 있는지 설명해줘."},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}",
                        "detail": "high"  # 또는 "low", "auto"
                    },
                },
            ],
        }
    ],
    max_tokens=100
)

print("🔹 GPT 응답:\n", response['choices'][0]['message']['content'])

usage = response["usage"]
prompt_tokens = usage["prompt_tokens"]
completion_tokens = usage["completion_tokens"]
total_tokens = usage["total_tokens"]

input_cost_usd = (prompt_tokens / 1000) * input_token_price_usd
output_cost_usd = (completion_tokens / 1000) * output_token_price_usd
total_cost_usd = input_cost_usd + output_cost_usd

total_cost_krw = total_cost_usd * usd_to_krw

print("\n 사용 토큰:")
print(f"  - 입력(prompt) 토큰: {prompt_tokens}")
print(f"  - 출력(completion) 토큰: {completion_tokens}")
print(f"  - 총 사용 토큰: {total_tokens}")

print("\n 비용:")
print(f"  - 총 예상 비용(USD): ${total_cost_usd:.6f}")
print(f"  - 총 예상 비용(KRW): 약 {total_cost_krw:.2f}원")