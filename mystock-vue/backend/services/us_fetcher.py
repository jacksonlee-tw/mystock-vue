import os
import json
import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import yfinance as yf
from typing import Optional, List

from config import get_target_stocks, get_months_range, DATA_DIR
from services.fetcher import fetch_status, load_stock_json
from db.dual_write import dual_write_daily_data, log_crawler_run

logger = logging.getLogger(__name__)

# 每檔股票要打 3 個各自獨立的 yfinance 網路請求（history/info/institutional_holders），
# 逐檔序列執行時等待時間會疊加；yfinance 底層走 requests，I/O 等待時會釋放 GIL，
# 用執行緒池併發跑可以把等待時間疊在一起而非累加。5 是相對保守的併發數，避免對
# Yahoo Finance 觸發限流；如需調整可視實測情況調高。
_US_FETCH_MAX_WORKERS = 5

def _safe_int(value) -> int:
    """yfinance 對未收盤或缺漏的交易日可能回傳 NaN，直接 int() 會拋出 ValueError，改成 0（見 CLAUDE.md 「缺漏改寫 0 而非中斷」慣例）。"""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0
    return int(value)

def stock_json_path(stock_id: str, market: str = "us") -> str:
    market_dir = os.path.join(DATA_DIR, market)
    os.makedirs(market_dir, exist_ok=True)
    return os.path.join(market_dir, f"{stock_id}.json")

def save_us_stock_json(stock_id: str, data: dict) -> None:
    path = stock_json_path(stock_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _fetch_and_save_symbol(symbol: str, ticker, mode: str, period: str) -> Optional[dict]:
    """抓取單一美股標的的 K 線＋籌碼並落地 JSON（每檔各自獨立的檔案，併發寫入互不衝突）。

    刻意不在這裡呼叫 dual_write_daily_data()：它底層的 StockRepository *_sync 方法
    每次都會 asyncio.run() 一個新事件迴圈，結束後 dispose 掉共用的背景連線池
    （見 repositories/stock_repository.py run_async() 的說明）；這個 dispose 是模組級
    全域狀態，多執行緒同時呼叫會互相搶著建立/釋放同一個 engine 而炸連線。因此雙寫
    一律留給呼叫端在主執行緒序列執行，這裡只回傳待寫入的資料。

    回傳 None 表示這檔沒有新資料或抓取失敗；否則回傳 {"symbol", "stock_data", "touched_dates"}
    供呼叫端落地 Postgres 雙寫。"""
    if not ticker:
        logger.warning(f"Ticker object for {symbol} not found in yfinance.")
        return None

    try:
        stock_data = load_stock_json(symbol, market="us")
        existing_dates = sorted(stock_data.keys())

        # 重抓模式忽略既有資料，一律以完整區間抓取，才能補回中間的缺漏
        if existing_dates and mode != "repair":
            start_date_str = existing_dates[-1]
            hist = ticker.history(start=start_date_str)
        else:
            hist = ticker.history(period=period)

        if hist.empty:
            return None

        # Fetch metadata & short interest
        info = ticker.info
        shares_short = info.get("sharesShort", 0)
        short_ratio = info.get("shortRatio", 0.0)
        name = info.get("shortName") or info.get("longName", symbol)

        # Fetch institutional holders
        inst_holders = 0
        try:
            holders_df = ticker.institutional_holders
            if holders_df is not None and not holders_df.empty:
                inst_holders = _safe_int(holders_df["Shares"].sum())
        except Exception:
            pass

        # Parse historical data
        for date_obj, row in hist.iterrows():
            date_key = date_obj.strftime("%Y-%m-%d")
            record = stock_data.get(date_key, {})

            record.update({
                "date": date_key,
                "symbol": symbol,
                "name": name,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": _safe_int(row["Volume"]),
                "amount": _safe_int(row["Volume"] * row["Close"])
            })
            stock_data[date_key] = record

        # Append static data (short interest, inst holders) to the latest date
        latest_date = hist.index[-1].strftime("%Y-%m-%d")
        if latest_date in stock_data:
            stock_data[latest_date]["short_interest"] = shares_short
            stock_data[latest_date]["short_ratio"] = short_ratio
            stock_data[latest_date]["institutional_holders"] = inst_holders

        save_us_stock_json(symbol, stock_data)

        touched_dates = [d.strftime("%Y-%m-%d") for d in hist.index]
        return {"symbol": symbol, "stock_data": stock_data, "touched_dates": touched_dates}

    except Exception as e:
        logger.error(f"Failed to fetch or save {symbol}: {e}")
        return None

def run_us_fetch_process(target_stocks: Optional[List[str]] = None, months: Optional[int] = None,
                         mode: str = "incremental", trigger_type: str = "manual"):
    stocks = target_stocks or get_target_stocks(market="us")
    started_at = datetime.now()
    try:
        m_range = months or get_months_range()

        mode_label = "重新抓取" if mode == "repair" else "增量更新"
        fetch_status.start(
            f"開始抓取美股資料 ({mode_label}) - 股票: {stocks}, 範圍: 近 {m_range} 個月"
        )

        days = m_range * 30
        period = "3mo" if days <= 90 else "6mo" if days <= 180 else "1y"

        total = len(stocks)
        updated_count = 0

        tickers = yf.Tickers(" ".join(stocks))

        # 抓取階段（history/info/institutional_holders 這三個各自獨立的網路請求）併發跑；
        # Postgres 雙寫留到這裡、在主執行緒序列執行，見 _fetch_and_save_symbol() 的說明。
        max_workers = min(_US_FETCH_MAX_WORKERS, total) or 1
        done = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_symbol = {
                executor.submit(_fetch_and_save_symbol, symbol, tickers.tickers.get(symbol), mode, period): symbol
                for symbol in stocks
            }
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                done += 1
                try:
                    result = future.result()
                except Exception as e:
                    logger.error(f"Failed to fetch or save {symbol}: {e}")
                    result = None

                if result:
                    updated_count += 1
                    stock_data = result["stock_data"]
                    touched_dates = result["touched_dates"]
                    dual_write_daily_data(
                        symbol, "us", {d: stock_data[d] for d in touched_dates if d in stock_data}
                    )

                fetch_status.update(done, total, f"已完成美股 ({symbol}) 行情及籌碼資料抓取 ({done}/{total})...")

        fetch_status.complete(f"美股資料更新完畢！共更新 {updated_count} 檔股票。")

        failed_count = total - updated_count
        if failed_count == 0:
            status = "success"
        elif updated_count == 0:
            status = "failed"
        else:
            status = "partial_failure"
        log_crawler_run("us", trigger_type, started_at, status,
                         symbols_success=updated_count, symbols_failed=failed_count)

    except Exception as e:
        fetch_status.fail(str(e))
        log_crawler_run("us", trigger_type, started_at, "failed", error_message=str(e))
