import httpx
import asyncio

TOKEN = "8735873560:AAERa9fZYBwdjtLGf32JEWSwiH5y4w5Anzc"

async def get_my_chat_id():
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    async with httpx.AsyncClient() as client:
        print("正在等待接收訊息...請去 Telegram 發個訊息給你的 Bot！")
        response = await client.get(url)
        data = response.json()
        
        if data["result"]:
            # 抓取最後一則訊息的發送者 ID
            chat_id = data["result"][-1]["message"]["from"]["id"]
            print(f"✨ 找到你的 Chat ID 了：{chat_id}")
        else:
            print("目前沒有收到訊息，請確認你是否已經對 Bot 按下 'Start' 並隨便傳個字。")

if __name__ == "__main__":
    asyncio.run(get_my_chat_id())