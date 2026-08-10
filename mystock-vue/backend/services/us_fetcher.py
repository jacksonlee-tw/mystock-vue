import os
import json
import logging
from datetime import datetime
import yfinance as yf
from typing import Optional, List

from config import get_target_stocks, get_months_range, DATA_DIR
from services.fetcher import fetch_status, load_stock_json

logger = logging.getLogger(__name__)

def stock_json_path(stock_id: str, market: str = "us") -> str:
    market_dir = os.path.join(DATA_DIR, market)
    os.makedirs(market_dir, exist_ok=True)
    return os.path.join(market_dir, f"{stock_id}.json")

def save_us_stock_json(stock_id: str, data: dict) -> None:
    path = stock_json_path(stock_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def run_us_fetch_process(target_stocks: Optional[List[str]] = None, months: Optional[int] = None):
    try:
        stocks = target_stocks or get_target_stocks(market="us")
        m_range = months or get_months_range()

        fetch_status.start(f"開始抓取美股資料 - 股票: {stocks}, 範圍: 近 {m_range} 個月")

        days = m_range * 30
        period = "3mo" if days <= 90 else "6mo" if days <= 180 else "1y"

        total = len(stocks)
        updated_count = 0
        
        tickers = yf.Tickers(" ".join(stocks))

        for idx, symbol in enumerate(stocks):
            fetch_status.update(idx + 1, total, f"正在抓取美股 ({symbol}) 行情及籌碼資料...")
            
            ticker = tickers.tickers.get(symbol)
            if not ticker:
                logger.warning(f"Ticker object for {symbol} not found in yfinance.")
                continue

            try:
                hist = ticker.history(period=period)
                if hist.empty:
                    continue

                stock_data = load_stock_json(symbol, market="us")
                
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
                        inst_holders = int(holders_df["Shares"].sum())
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
                        "volume": int(row["Volume"]),
                        "amount": int(row["Volume"] * row["Close"])
                    })
                    stock_data[date_key] = record

                # Append static data (short interest, inst holders) to the latest date
                latest_date = hist.index[-1].strftime("%Y-%m-%d")
                if latest_date in stock_data:
                    stock_data[latest_date]["short_interest"] = shares_short
                    stock_data[latest_date]["short_ratio"] = short_ratio
                    stock_data[latest_date]["institutional_holders"] = inst_holders

                save_us_stock_json(symbol, stock_data)
                updated_count += 1
                
            except Exception as e:
                logger.error(f"Failed to fetch or save {symbol}: {e}")

        fetch_status.complete(f"美股資料更新完畢！共更新 {updated_count} 檔股票。")

    except Exception as e:
        fetch_status.fail(str(e))
