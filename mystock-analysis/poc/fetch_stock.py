import httpx
import pandas as pd
import time
from datetime import datetime

def fetch_twse_stock_day(stock_id: str, date_str: str):
    """
    抓取指定個股當月的日成交資訊
    :param stock_id: 股票代碼 (例如: '2330')
    :param date_str: 查詢日期 (格式: '20260301', 證交所會回傳該月全月份資料)
    """
    # 證交所 API 網址
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    
    params = {
        "response": "json",
        "date": date_str,
        "stockNo": stock_id
    }
    
    # 模擬瀏覽器 Header，避免被證交所阻擋 (反爬蟲基本工)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print(f"🔍 正在從證交所抓取 {stock_id} 在 {date_str} 的資料...")

    with httpx.Client(headers=headers, timeout=10.0) as client:
        response = client.get(url, params=params)
        
        if response.status_code != 200:
            print(f"❌ 請求失敗，狀態碼: {response.status_code}")
            return None

        data = response.json()

        if data.get("stat") != "OK":
            print(f"❌ 證交所回傳錯誤: {data.get('stat')}")
            return None

        # 整理成 Pandas DataFrame
        columns = data["fields"]
        rows = data["data"]
        df = pd.DataFrame(rows, columns=columns)
        
        # 簡單清理：移除成交量中的逗號並轉為數字
        df["收盤價"] = df["收盤價"].str.replace(",", "").astype(float)
        df["成交股數"] = df["成交股數"].str.replace(",", "").astype(int)
        
        return df

if __name__ == "__main__":
    # 測試抓取台積電 (2330)
    target_stock = "2330"
    current_date = datetime.now().strftime("%Y%m%d") # 今天的日期
    
    try:
        result_df = fetch_twse_stock_day(target_stock, current_date)
        
        if result_df is not None:
            print("\n✅ 抓取成功！最新 5 筆資料如下：")
            print(result_df.tail(5)[["日期", "成交股數", "開盤價", "最高價", "最低價", "收盤價"]])
            
            # 這裡可以加入簡單的邏輯判斷
            last_price = result_df.iloc[-1]["收盤價"]
            print(f"\n💡 {target_stock} 最新收盤價為: {last_price}")
            
    except Exception as e:
        print(f"💥 執行時發生錯誤: {e}")
    
    # 提醒：頻繁抓取會被證交所鎖 IP，建議正式使用時加入 time.sleep()