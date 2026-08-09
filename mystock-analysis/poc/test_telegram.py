import asyncio
import httpx

# --- 請填入你的資訊 ---
TOKEN = "8735873560:AAERa9fZYBwdjtLGf32JEWSwiH5y4w5Anzc"
CHAT_ID = "8712141524"
# ---------------------

async def send_telegram_msg(message: str):
    """
    這是一個獨立的測試函式，未來可以直接複製到 FastAPI 的 utility 中
    """
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML" # 支援 <b>粗體</b> 等格式
    }

    print(f"正在發送測試訊息至 Telegram...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=10.0)
            response.raise_for_status() # 如果狀態碼不是 200 會拋出異常
            
            result = response.json()
            if result.get("ok"):
                print("✅ 發送成功！請檢查你的手機 Telegram。")
            else:
                print(f"❌ 發送失敗，錯誤原因: {result.get('description')}")
                
        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP 錯誤: {e.response.status_code}")
        except Exception as e:
            print(f"❌ 發生未知錯誤: {e}")

if __name__ == "__main__":
    # 模擬股票警示訊息
    test_content = (
        "🚀 <b>個人股票分析系統測試</b>\n"
        "--------------------------\n"
        "指標：RSI 觸底回升, 大漲500點\n"
        "狀態：連線測試正常"
    )
    
    # 執行非同步主程式
    asyncio.run(send_telegram_msg(test_content))
