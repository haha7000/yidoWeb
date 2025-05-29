import openai
import os

def LotteClassificationUseGpt(ocr_text: str) -> str:
    SYSTEM_PROMPT = open("/Users/gimdonghun/Documents/DbTest/LottePrompt.txt", "r").read()
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