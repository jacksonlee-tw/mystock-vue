import asyncio
import httpx
import yfinance as yf
import pandas as pd

# --- Telegram 設定（建議改用環境變數管理）---
TOKEN = "8735873560:AAERa9fZYBwdjtLGf32JEWSwiH5y4w5Anzc"
CHAT_ID = "8712141524"

# --- 監控股票清單（台股加 .TW 後綴）---
WATCH_LIST = ["2330.TW", "2317.TW", "2454.TW", "3231.TW", "2382.TW"]


# ── 股票資料抓取 ──────────────────────────────────────────────
def fetch_watch_stocks() -> pd.DataFrame:
    """用 yfinance 只抓 watchlist 的今日行情（不下載全市場）"""
    tickers = yf.Tickers(" ".join(WATCH_LIST))
    rows = []
    for symbol, ticker in tickers.tickers.items():
        info = ticker.fast_info
        last = info.last_price
        prev = info.previous_close
        change = round(last - prev, 2) if last and prev else None
        change_pct = round((last - prev) / prev * 100, 2) if last and prev else None
        rows.append({
            "股號": symbol.replace(".TW", ""),
            "名稱": ticker.info.get("shortName", symbol),
            "開盤價": info.open,
            "最高價": info.day_high,
            "最低價": info.day_low,
            "收盤價": last,
            "昨收": prev,
            "漲跌": change,
            "漲跌幅": change_pct,
        })
    return pd.DataFrame(rows)


# ── 訊息格式化 ────────────────────────────────────────────────
def format_telegram_message(df: pd.DataFrame) -> str:
    """將 DataFrame 格式化為 Telegram HTML 訊息"""
    lines = ["📊 <b>股票行情日報</b>", ""]

    for _, row in df.iterrows():
        change = row["漲跌"] or 0
        pct = row["漲跌幅"] or 0
        if change > 0:
            sign, icon = "+", "🔺"
        elif change < 0:
            sign, icon = "", "🔻"
        else:
            sign, icon = "", "➖"

        lines.append(
            f"{icon} <b>{row['股號']} {row['名稱']}</b>\n"
            f"   收盤：<b>{row['收盤價']}</b>　"
            f"漲跌：{sign}{change} ({sign}{pct}%)\n"
            f"   開：{row['開盤價']}　高：{row['最高價']}　低：{row['最低價']}"
        )

    lines.append("")
    lines.append("─────────────────────")
    lines.append(f"更新時間：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
    return "\n".join(lines)


# ── Telegram 發送 ─────────────────────────────────────────────
async def send_telegram_msg(message: str) -> bool:
    """發送訊息到 Telegram，回傳是否成功"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=10.0)
        response.raise_for_status()
        result = response.json()
        return result.get("ok", False)


# ── 主流程 ────────────────────────────────────────────────────
async def main():
    print(f"🚀 抓取行情：{WATCH_LIST}")

    try:
        df = fetch_watch_stocks()
    except Exception as e:
        print(f"❌ 行情抓取失敗：{e}")
        return

    if df.empty:
        print("❌ 未取得任何資料（可能今日休市）")
        return

    # 印出終端預覽
    display_cols = ["股號", "名稱", "收盤價", "漲跌", "漲跌幅"]
    print(df[display_cols].to_string(index=False))

    # 發送 Telegram
    msg = format_telegram_message(df)
    print("\n正在發送 Telegram 訊息...")
    try:
        ok = await send_telegram_msg(msg)
        if ok:
            print("✅ Telegram 發送成功！")
        else:
            print("❌ Telegram 回應 ok=false")
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP 錯誤：{e.response.status_code}")
    except Exception as e:
        print(f"❌ 發送失敗：{e}")


if __name__ == "__main__":
    asyncio.run(main())
