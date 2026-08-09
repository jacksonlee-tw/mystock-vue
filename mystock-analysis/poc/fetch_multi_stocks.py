import yfinance as yf
import pandas as pd

# 定義你想追蹤的股票清單（台股加 .TW 後綴）
WATCH_LIST = ["2330.TW", "2317.TW", "2454.TW", "3231.TW", "2382.TW"]


def fetch_watch_stocks() -> pd.DataFrame:
    """用 yfinance 只抓 watchlist 的今日行情（不下載全市場）"""
    tickers = yf.Tickers(" ".join(WATCH_LIST))
    rows = []
    for symbol, ticker in tickers.tickers.items():
        info = ticker.fast_info
        rows.append({
            "股號": symbol.replace(".TW", ""),
            "名稱": ticker.info.get("shortName", symbol),
            "開盤價": info.open,
            "最高價": info.day_high,
            "最低價": info.day_low,
            "收盤價": info.last_price,
            "昨收": info.previous_close,
            "漲跌": round(info.last_price - info.previous_close, 2) if info.last_price and info.previous_close else None,
            "成交量(股)": info.three_month_average_volume,
        })
    return pd.DataFrame(rows)


def main():
    print(f"🚀 用 yfinance 抓取監控清單行情：{WATCH_LIST}")
    print("-" * 60)

    try:
        df = fetch_watch_stocks()
    except Exception as e:
        print(f"❌ 資料抓取失敗：{e}")
        return

    if df.empty:
        print("❌ 未取得任何資料")
        return

    display_cols = ["股號", "名稱", "開盤價", "最高價", "最低價", "收盤價", "漲跌", "成交量(股)"]

    for _, row in df.iterrows():
        sign = "▲" if (row["漲跌"] or 0) > 0 else ("▼" if (row["漲跌"] or 0) < 0 else "-")
        print(f"✅ {row['股號']} {row['名稱']} | 收盤：{row['收盤價']} {sign}{abs(row['漲跌'] or 0)}")

    print("\n" + "=" * 22 + " 今日行情彙整 " + "=" * 22)
    print(df[display_cols].to_string(index=False))
    print("=" * 58)


if __name__ == "__main__":
    main()