import os
from google import genai

# 1. 初始化 Client（API Key 由環境變數 GEMINI_API_KEY 取得）
client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))

def ask_gemini(prompt):
    try:
        # 2. 呼叫模型 (建議使用最新穩定的 gemini-2.0-flash 或更新版本)
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt
        )
        
        # 3. 印出結果
        print(f"Gemini 回覆：\n{response.text}")
        
    except Exception as e:
        print(f"發生錯誤：{e}")

if __name__ == "__main__":
    user_input = input("請輸入你想問 Gemini 的問題：")
    ask_gemini(user_input)