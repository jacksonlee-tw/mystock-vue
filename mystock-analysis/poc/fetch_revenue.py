import httpx
import pandas as pd
import io
from datetime import datetime

# 你關注的族群清單
MY_STOCKS = ["2313", "3491", "2314", "3081", "4979", "6442"]

def fetch_monthly_revenue(year: int, month: int):
    """
    抓取指定月份的全市場營收彙總表 (上市)
    注意：證交所資料通常在每月 10 號後完整更新前一個月的資料
    """
    # 轉換為民國年
    roc_year = year - 1911
    url = f"https://mops.twse.com.tw/nas/t21/sbi/t21sc03_{roc_year}_{month}_0.html"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print(f"📊 正在抓取 {year}/{month} 營收資料...")
    
    try:
        with httpx.Client(headers=headers, timeout=20.0, verify=False) as client:
            response = client.get(url)
            print(f"   HTTP {response.status_code}  URL: {url}")
            if response.status_code != 200:
                print(f"❌ HTTP 狀態碼非 200，可能該月資料尚未公告")
                return None

            dfs = pd.read_html(io.StringIO(response.text), encoding="utf-8")
            print(f"   找到 {len(dfs)} 個表格")

            result_frames = []
            for i, df in enumerate(dfs):
                # 先壓平 MultiIndex 欄位
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(-1)
                # 過濾含「公司代號」的表格
                if "公司代號" in df.columns:
                    result_frames.append(df)

            if not result_frames:
                # 找不到時印出前幾個表格的欄位供診斷
                print("⚠️  找不到含「公司代號」欄位的表格，印出前 3 個表格欄位：")
                for i, df in enumerate(dfs[:3]):
                    cols = df.columns.tolist()
                    print(f"   表格[{i}] 欄位: {cols[:8]}")
                return None

            combined_df = pd.concat(result_frames, ignore_index=True)
            combined_df["公司代號"] = combined_df["公司代號"].astype(str).str.strip()
            print(f"   合併後共 {len(combined_df)} 筆，欄位：{combined_df.columns.tolist()[:6]}")
            return combined_df

    except Exception as e:
        print(f"❌ 抓取失敗: {e}")
        return None

def analyze_revenue_growth(df, watch_list):
    """
    篩選清單並分析 YoY (去年同月增減)
    """
    target_df = df[df["公司代號"].isin(watch_list)].copy()
    
    # 挑選重點欄位
    # 欄位說明：當月營收, 上月營收, 去年同月營收, 上月比較增減(%), 去年同月增減(%)
    report = target_df[["公司代號", "公司名稱", "當月營收", "去年同月增減(%)"]].copy()
    
    # 轉為數值型態方便判斷
    report["去年同月增減(%)"] = pd.to_numeric(report["去年同月增減(%)"], errors='coerce')
    
    return report

if __name__ == "__main__":
    # 假設現在是 2026 年 3 月，我們抓 2 月的資料 (因 3 月營收要到 4/10 才公告)
    data = fetch_monthly_revenue(2026, 2)
    
    if data is not None:
        result = analyze_revenue_growth(data, MY_STOCKS)
        print("\n🚀 「低軌衛星/光通訊」營收成長追蹤：")
        print(result.to_string(index=False))
        
        # 簡單邏輯：YoY > 20% 標註強勢
        strong_growth = result[result["去年同月增減(%)"] > 20]
        if not strong_growth.empty:
            print(f"\n💡 發現成長強勁標的：{', '.join(strong_growth['公司名稱'].tolist())}")