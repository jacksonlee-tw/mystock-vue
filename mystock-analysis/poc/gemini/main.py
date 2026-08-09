# To run this code you need to install the following dependencies:
# pip install google-genai

import os
import time
from google import genai
from google.genai import types
from google.genai.errors import ClientError


def generate(user_input: str, retries: int = 3, backoff: float = 10.0):
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    model = "gemini-3-flash-preview"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=user_input),
            ],
        ),
    ]
    tools = [
        types.Tool(googleSearch=types.GoogleSearch()),
    ]
    generate_content_config = types.GenerateContentConfig(
        tools=tools,
    )

    for attempt in range(1, retries + 1):
        try:
            for chunk in client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=generate_content_config,
            ):
                if text := chunk.text:
                    print(text, end="")
            print()  # 換行
            return
        except ClientError as e:
            if e.status_code == 429 and attempt < retries:
                wait = backoff * attempt
                print(f"\n[警告] API 配額不足（429），{wait:.0f} 秒後重試（第 {attempt}/{retries - 1} 次）...")
                time.sleep(wait)
            else:
                raise


if __name__ == "__main__":
    user_input = input("請輸入你想問 Gemini 的問題：")
    generate(user_input)


