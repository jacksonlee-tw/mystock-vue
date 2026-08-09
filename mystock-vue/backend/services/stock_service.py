import os
import json
import calendar
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from config import DATA_DIR, get_target_stocks
from services.fetcher import stock_json_path, load_stock_json

# 定義欄位分類
SUM_FIELDS = [
    "外資買賣超(張)", "投信買賣超(張)", "自營商買賣超(張)", "合計買賣超(張)",
    "估算買賣超金額(萬元)", "成交股數(股)", "成交金額(元)", "成交筆數(筆)"
]

END_FIELDS = ["收盤價", "融資餘額(張)", "融券餘額(張)"]
START_FIELDS = ["開盤價"]
MAX_FIELDS = ["最高價"]
MIN_FIELDS = ["最低價"]

def months_ago(months: int, from_date: Optional[datetime] = None) -> datetime:
    base = from_date or datetime.now()
    month_index = base.month - 1 - months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return base.replace(year=year, month=month, day=day)

def discover_available_stocks() -> List[Dict[str, Any]]:
    """掃描 data/ 目錄下的股票 JSON 檔，回傳股票清單與元資料。"""
    if not os.path.exists(DATA_DIR):
        return []
        
    stocks = []
    tracked_codes = set(get_target_stocks())

    for filename in sorted(os.listdir(DATA_DIR)):
        if filename.startswith("_") or not filename.endswith(".json"):
            continue
        stock_id = filename[:-5]
        file_path = os.path.join(DATA_DIR, filename)
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict) or not data:
                    continue
                    
                sorted_dates = sorted(data.keys())
                latest_date = sorted_dates[-1]
                latest_record = data[latest_date]
                stock_name = latest_record.get("股票名稱", stock_id)
                close_price = latest_record.get("收盤價", 0.0)

                stocks.append({
                    "stock_id": stock_id,
                    "stock_name": stock_name,
                    "latest_date": latest_date,
                    "latest_close": close_price,
                    "total_records": len(sorted_dates),
                    "is_tracked": stock_id in tracked_codes
                })
        except Exception:
            continue
            
    return stocks

def get_heatmap_data(period: str = "daily") -> List[Dict[str, Any]]:
    """掃描 data/ 目錄下的股票 JSON 檔，回傳供熱力圖使用的資料（包含最新報價、漲跌與 Sparkline）。"""
    if not os.path.exists(DATA_DIR):
        return []
        
    stocks = []
    tracked_codes = set(get_target_stocks())

    for filename in sorted(os.listdir(DATA_DIR)):
        if filename.startswith("_") or not filename.endswith(".json"):
            continue
        stock_id = filename[:-5]
        if stock_id not in tracked_codes:
            continue
            
        file_path = os.path.join(DATA_DIR, filename)
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict) or not data:
                    continue
                
                # Use aggregate_stock_data to get the period aggregated data
                # Heatmap usually only needs recent data, so we can limit to 6 months
                aggregated = aggregate_stock_data(data, period=period, months=6)
                if not aggregated:
                    continue
                
                latest_record = aggregated[-1]
                stock_name = latest_record.get("股票名稱", stock_id)
                close_price = latest_record.get("收盤價", 0.0)
                latest_date = latest_record.get("日期", "")
                
                if len(aggregated) >= 2:
                    prev_record = aggregated[-2]
                    prev_close = prev_record.get("收盤價", 0.0)
                else:
                    prev_close = latest_record.get("開盤價", close_price)
                
                change = close_price - prev_close
                change_percent = (change / prev_close * 100) if prev_close > 0 else 0
                
                # Sparkline data (last 10 periods)
                sparkline_records = aggregated[-10:]
                sparkline = [r.get("收盤價", 0.0) for r in sparkline_records]
                start_date = sparkline_records[0].get("日期", "") if sparkline_records else ""
                end_date = sparkline_records[-1].get("日期", "") if sparkline_records else ""

                stocks.append({
                    "stock_id": stock_id,
                    "stock_name": stock_name,
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
    """依據 period 計算聚合的 Group Key (YYYY-MM-DD, YYYY-Www, YYYY-MM)"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if period == "weekly":
        # ISO 週數：使用週一為起始日
        year, week, _ = dt.isocalendar()
        return f"{year}-W{week:02d}"
    elif period == "monthly":
        return dt.strftime("%Y-%m")
    return date_str

def aggregate_stock_data(data: Dict[str, Any], period: str = "daily", months: int = 3) -> List[Dict[str, Any]]:
    """
    讀取單檔股票 JSON 資料，進行時間過濾與週期聚合。
    """
    if not data:
        return []

    cutoff_date = months_ago(months).strftime("%Y-%m-%d")
    sorted_dates = [d for d in sorted(data.keys()) if d >= cutoff_date]

    if period == "daily":
        result = []
        for date_key in sorted_dates:
            rec = dict(data[date_key])
            rec["日期"] = date_key
            # 計算券資比
            margin_long = rec.get("融資餘額(張)", 0)
            margin_short = rec.get("融券餘額(張)", 0)
            rec["券資比(%)"] = round((margin_short / margin_long) * 100, 2) if margin_long > 0 else None
            result.append(rec)
        return result

    # 週線/月線 聚合處理
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for date_key in sorted_dates:
        g_key = _get_group_key(date_key, period)
        rec = dict(data[date_key])
        rec["日期"] = date_key
        groups.setdefault(g_key, []).append(rec)

    result = []
    for g_key, records in groups.items():
        # sorted by date inside group
        records.sort(key=lambda r: r["日期"])

        stock_id = records[0].get("股票代號", "")
        stock_name = records[0].get("股票名稱", "")
        end_date = records[-1]["日期"]  # 該週/月的最後一日交易日

        aggregated: Dict[str, Any] = {
            "日期": end_date,
            "period_label": g_key,
            "股票名稱": stock_name,
        }

        # 1. 流量欄位：加總
        for f in SUM_FIELDS:
            aggregated[f] = sum(r.get(f, 0) for r in records)

        # 2. 存量與收盤價：取期間最後一筆有效值
        for f in END_FIELDS:
            valid_vals = [r[f] for r in records if f in r and r[f] is not None]
            aggregated[f] = valid_vals[-1] if valid_vals else 0

        # 3. K 線圖開盤價：取期間第一筆有效值
        for f in START_FIELDS:
            valid_vals = [r[f] for r in records if f in r and r[f] is not None and r[f] > 0]
            aggregated[f] = valid_vals[0] if valid_vals else (records[0].get("收盤價", 0))

        # 4. K 線圖最高價：取最大值
        for f in MAX_FIELDS:
            valid_vals = [r[f] for r in records if f in r and r[f] is not None]
            aggregated[f] = max(valid_vals) if valid_vals else 0

        # 5. K 線圖最低價：取非零最小值
        for f in MIN_FIELDS:
            valid_vals = [r[f] for r in records if f in r and r[f] is not None and r[f] > 0]
            aggregated[f] = min(valid_vals) if valid_vals else (aggregated.get("收盤價", 0))

        # 6. 券資比 (%)：聚合後期末融券 / 期末融資
        m_long = aggregated.get("融資餘額(張)", 0)
        m_short = aggregated.get("融券餘額(張)", 0)
        aggregated["券資比(%)"] = round((m_short / m_long) * 100, 2) if m_long > 0 else None

        result.append(aggregated)

    return result

def get_stock_chart_payload(stock_id: str, period: str = "daily", months: int = 3) -> Dict[str, Any]:
    """為前端圖表建立預先格式化的 Series 資料體"""
    raw_data = load_stock_json(stock_id)
    if not raw_data:
        return {"error": f"找不到股票 {stock_id} 的數據資料"}

    aggregated_records = aggregate_stock_data(raw_data, period=period, months=months)
    if not aggregated_records:
        return {"error": "指定時間範圍內無數據"}

    dates = [r["日期"] for r in aggregated_records]
    stock_name = aggregated_records[0].get("股票名稱", stock_id)

    # K 線圖 (OHLC) [Open, Close, Low, High]
    kline_data = [
        [r.get("開盤價", 0), r.get("收盤價", 0), r.get("最低價", 0), r.get("最高價", 0)]
        for r in aggregated_records
    ]

    # 三大法人買賣超
    foreign = [r.get("外資買賣超(張)", 0) for r in aggregated_records]
    trust = [r.get("投信買賣超(張)", 0) for r in aggregated_records]
    dealer = [r.get("自營商買賣超(張)", 0) for r in aggregated_records]
    total_institutional = [r.get("合計買賣超(張)", 0) for r in aggregated_records]
    estimated_amount = [r.get("估算買賣超金額(萬元)", 0) for r in aggregated_records]

    # 融資融券
    margin_long = [r.get("融資餘額(張)", 0) for r in aggregated_records]
    margin_short = [r.get("融券餘額(張)", 0) for r in aggregated_records]
    short_ratio = [r.get("券資比(%)") for r in aggregated_records]

    # 最新指標摘要
    latest = aggregated_records[-1]

    start_date = dates[0] if dates else ""
    end_date = dates[-1] if dates else ""

    return {
        "stock_id": stock_id,
        "stock_name": stock_name,
        "period": period,
        "months": months,
        "start_date": start_date,
        "end_date": end_date,
        "dates": dates,
        "latest_summary": {
            "date": latest["日期"],
            "close": latest.get("收盤價", 0),
            "open": latest.get("開盤價", 0),
            "high": latest.get("最高價", 0),
            "low": latest.get("最低價", 0),
            "foreign": latest.get("外資買賣超(張)", 0),
            "trust": latest.get("投信買賣超(張)", 0),
            "dealer": latest.get("自營商買賣超(張)", 0),
            "total_institutional": latest.get("合計買賣超(張)", 0),
            "estimated_amount_wan": latest.get("估算買賣超金額(萬元)", 0),
            "margin_long": latest.get("融資餘額(張)", 0),
            "margin_short": latest.get("融券餘額(張)", 0),
            "short_ratio": latest.get("券資比(%)")
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
