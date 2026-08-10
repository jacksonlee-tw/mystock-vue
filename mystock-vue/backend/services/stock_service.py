import os
import json
import calendar
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from config import DATA_DIR, get_target_stocks, get_enabled_markets
from services.fetcher import load_stock_json

# 定義欄位分類 (已轉換為英文鍵名)
SUM_FIELDS = [
    "foreign_buy_sell", "trust_buy_sell", "dealer_buy_sell", "institutional_total",
    "institutional_amount_est", "volume", "amount", "trades"
]

END_FIELDS = ["close", "margin_balance", "short_balance"]
START_FIELDS = ["open"]
MAX_FIELDS = ["high"]
MIN_FIELDS = ["low"]

def months_ago(months: int, from_date: Optional[datetime] = None) -> datetime:
    base = from_date or datetime.now()
    month_index = base.month - 1 - months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return base.replace(year=year, month=month, day=day)

def discover_available_stocks() -> List[Dict[str, Any]]:
    """掃描 data/{market}/ 目錄下的股票 JSON 檔，回傳股票清單與元資料。"""
    stocks = []
    
    for market in get_enabled_markets():
        market_dir = os.path.join(DATA_DIR, market)
        if not os.path.exists(market_dir):
            continue
            
        tracked_codes = set(get_target_stocks(market=market))
        
        for filename in sorted(os.listdir(market_dir)):
            if filename.startswith("_") or not filename.endswith(".json"):
                continue
            stock_id = filename[:-5]
            file_path = os.path.join(market_dir, filename)
            
            try:
                data = load_stock_json(stock_id, market)
                if not data:
                    continue
                    
                sorted_dates = sorted(data.keys())
                latest_date = sorted_dates[-1]
                latest_record = data[latest_date]
                stock_name = latest_record.get("name", stock_id)
                close_price = latest_record.get("close", 0.0)

                stocks.append({
                    "stock_id": stock_id,
                    "stock_name": stock_name,
                    "market": market,
                    "latest_date": latest_date,
                    "latest_close": close_price,
                    "total_records": len(sorted_dates),
                    "is_tracked": stock_id in tracked_codes
                })
            except Exception:
                continue
                
    return stocks

def get_heatmap_data(period: str = "daily", market: Optional[str] = None) -> List[Dict[str, Any]]:
    """掃描 data/{market}/ 目錄下的股票 JSON 檔，回傳供熱力圖使用的資料（包含最新報價、漲跌與 Sparkline）。"""
    stocks = []
    
    enabled_markets = [market] if market and market in get_enabled_markets() else get_enabled_markets()
    for m in enabled_markets:
        market_dir = os.path.join(DATA_DIR, m)
        if not os.path.exists(market_dir):
            continue
            
        tracked_codes = set(get_target_stocks(market=m))
        
        for filename in sorted(os.listdir(market_dir)):
            if filename.startswith("_") or not filename.endswith(".json"):
                continue
            stock_id = filename[:-5]
            if stock_id not in tracked_codes:
                continue
                
            file_path = os.path.join(market_dir, filename)
            
            try:
                data = load_stock_json(stock_id, m)
                if not data:
                    continue
                
                aggregated = aggregate_stock_data(data, period=period, months=6)
                if not aggregated:
                    continue
                
                latest_record = aggregated[-1]
                stock_name = latest_record.get("name", stock_id)
                close_price = latest_record.get("close", 0.0)
                latest_date = latest_record.get("date", "")
                
                if len(aggregated) >= 2:
                    prev_record = aggregated[-2]
                    prev_close = prev_record.get("close", 0.0)
                else:
                    prev_close = latest_record.get("open", close_price)
                
                change = close_price - prev_close
                change_percent = (change / prev_close * 100) if prev_close > 0 else 0
                
                sparkline_records = aggregated[-10:]
                sparkline = [r.get("close", 0.0) for r in sparkline_records]
                start_date = sparkline_records[0].get("date", "") if sparkline_records else ""
                end_date = sparkline_records[-1].get("date", "") if sparkline_records else ""

                stocks.append({
                    "stock_id": stock_id,
                    "stock_name": stock_name,
                    "market": m,
                    "start_date": start_date,
                    "end_date": end_date,
                    "latest_date": latest_date,
                    "latest_close": close_price,
                    "change": round(change, 2),
                    "change_percent": round(change_percent, 2),
                    "sparkline": sparkline
                })

            except Exception:
                continue
                
    return stocks

def _get_group_key(date_str: str, period: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if period == "weekly":
        year, week, _ = dt.isocalendar()
        return f"{year}-W{week:02d}"
    elif period == "monthly":
        return dt.strftime("%Y-%m")
    return date_str

def aggregate_stock_data(data: Dict[str, Any], period: str = "daily", months: int = 3) -> List[Dict[str, Any]]:
    if not data:
        return []

    cutoff_date = months_ago(months).strftime("%Y-%m-%d")
    sorted_dates = [d for d in sorted(data.keys()) if d >= cutoff_date]

    if period == "daily":
        result = []
        for date_key in sorted_dates:
            rec = dict(data[date_key])
            rec["date"] = date_key
            margin_long = rec.get("margin_balance", 0)
            margin_short = rec.get("short_balance", 0)
            rec["short_ratio"] = round((margin_short / margin_long) * 100, 2) if margin_long > 0 else None
            result.append(rec)
        return result

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for date_key in sorted_dates:
        g_key = _get_group_key(date_key, period)
        rec = dict(data[date_key])
        rec["date"] = date_key
        groups.setdefault(g_key, []).append(rec)

    result = []
    for g_key, records in groups.items():
        records.sort(key=lambda r: r["date"])

        stock_id = records[0].get("symbol", "")
        stock_name = records[0].get("name", "")
        end_date = records[-1]["date"]

        aggregated: Dict[str, Any] = {
            "date": end_date,
            "period_label": g_key,
            "name": stock_name,
            "symbol": stock_id
        }

        for f in SUM_FIELDS:
            aggregated[f] = sum(r.get(f, 0) for r in records)

        for f in END_FIELDS:
            valid_vals = [r[f] for r in records if f in r and r[f] is not None]
            aggregated[f] = valid_vals[-1] if valid_vals else 0

        for f in START_FIELDS:
            valid_vals = [r[f] for r in records if f in r and r[f] is not None and r[f] > 0]
            aggregated[f] = valid_vals[0] if valid_vals else (records[0].get("close", 0))

        for f in MAX_FIELDS:
            valid_vals = [r[f] for r in records if f in r and r[f] is not None]
            aggregated[f] = max(valid_vals) if valid_vals else 0

        for f in MIN_FIELDS:
            valid_vals = [r[f] for r in records if f in r and r[f] is not None and r[f] > 0]
            aggregated[f] = min(valid_vals) if valid_vals else (aggregated.get("close", 0))

        m_long = aggregated.get("margin_balance", 0)
        m_short = aggregated.get("short_balance", 0)
        aggregated["short_ratio"] = round((m_short / m_long) * 100, 2) if m_long > 0 else None

        result.append(aggregated)

    return result

def get_stock_chart_payload(stock_id: str, period: str = "daily", months: int = 3, market: str = "tw") -> Dict[str, Any]:
    raw_data = load_stock_json(stock_id, market)
    if not raw_data:
        return {"error": f"找不到股票 {stock_id} 的數據資料"}

    aggregated_records = aggregate_stock_data(raw_data, period=period, months=months)
    if not aggregated_records:
        return {"error": "指定時間範圍內無數據"}

    dates = [r["date"] for r in aggregated_records]
    stock_name = aggregated_records[0].get("name", stock_id)

    kline_data = [
        [r.get("open", 0), r.get("close", 0), r.get("low", 0), r.get("high", 0)]
        for r in aggregated_records
    ]

    foreign = [r.get("foreign_buy_sell", 0) for r in aggregated_records]
    trust = [r.get("trust_buy_sell", 0) for r in aggregated_records]
    dealer = [r.get("dealer_buy_sell", 0) for r in aggregated_records]
    total_institutional = [r.get("institutional_total", 0) for r in aggregated_records]
    estimated_amount = [r.get("institutional_amount_est", 0) for r in aggregated_records]

    margin_long = [r.get("margin_balance", 0) for r in aggregated_records]
    margin_short = [r.get("short_balance", 0) for r in aggregated_records]
    short_ratio = [r.get("short_ratio") for r in aggregated_records]

    latest = aggregated_records[-1]

    start_date = dates[0] if dates else ""
    end_date = dates[-1] if dates else ""

    return {
        "stock_id": stock_id,
        "stock_name": stock_name,
        "market": market,
        "period": period,
        "months": months,
        "start_date": start_date,
        "end_date": end_date,
        "dates": dates,
        "latest_summary": {
            "date": latest["date"],
            "close": latest.get("close", 0),
            "open": latest.get("open", 0),
            "high": latest.get("high", 0),
            "low": latest.get("low", 0),
            "foreign_buy_sell": latest.get("foreign_buy_sell", 0),
            "trust_buy_sell": latest.get("trust_buy_sell", 0),
            "dealer_buy_sell": latest.get("dealer_buy_sell", 0),
            "institutional_total": latest.get("institutional_total", 0),
            "institutional_amount_est": latest.get("institutional_amount_est", 0),
            "margin_balance": latest.get("margin_balance", 0),
            "short_balance": latest.get("short_balance", 0),
            "short_ratio": latest.get("short_ratio"),
            "short_interest": latest.get("short_interest", 0),
            "institutional_holders": latest.get("institutional_holders", 0),
            # backward compatibility for old frontend code expecting these exact keys
            "foreign": latest.get("foreign_buy_sell", 0),
            "trust": latest.get("trust_buy_sell", 0),
            "dealer": latest.get("dealer_buy_sell", 0)
        },
        "kline": kline_data,
        "institutional": {
            "foreign": foreign,
            "trust": trust,
            "dealer": dealer,
            "total": total_institutional,
            "estimated_amount": estimated_amount
        },
        "margin": {
            "long_balance": margin_long,
            "short_balance": margin_short,
            "short_ratio": short_ratio
        },
        "records": aggregated_records
    }
