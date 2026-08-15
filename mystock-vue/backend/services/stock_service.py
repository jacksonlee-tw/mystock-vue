import os
import json
import calendar
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from config import DATA_DIR, get_target_stocks, get_enabled_markets, get_data_source
from services.fetcher import load_stock_json
from db.mapping import daily_row_to_record
from repositories.stock_repository import StockRepository
from indicators.moving_average import compute_ma_set

# 定義欄位分類 (已轉換為英文鍵名)
SUM_FIELDS = [
    "foreign_buy_sell", "trust_buy_sell", "dealer_buy_sell", "institutional_total",
    "institutional_amount_est", "volume", "amount", "trades"
]

# 均線策略警示系統 設計文件第 4 節「均線參數矩陣」的預設週期。獨立宣告於此（而非 import
# strategies 套件），避免 services ↔ strategies 之間形成循環匯入（strategies/chip_provider.py
# 本身就是靠呼叫 stock_service 取資料）。
MA_PERIODS = [5, 10, 20, 60, 120, 240]

END_FIELDS = ["margin_balance", "short_balance"]  # 餘額類欄位，0 是合法值，直接採最後一筆
PRICE_END_FIELDS = ["close"]  # 收盤價 0 代表當天未回補到行情，須排除，改採最後一筆「有效」值
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

def _list_stock_ids_json(market_dir: str) -> List[str]:
    if not os.path.exists(market_dir):
        return []
    return [
        f[:-5] for f in sorted(os.listdir(market_dir))
        if not f.startswith("_") and f.endswith(".json")
    ]

async def _list_stock_ids_db(market: str) -> List[str]:
    symbols = await StockRepository().list_symbols(market_type=market)
    return [s["symbol"] for s in symbols]

async def load_stock_data(stock_id: str, market: str = "tw", source: Optional[str] = None,
                           kind: str = "stock") -> dict:
    """讀取單一標的的每日資料；依 DATA_SOURCE 決定讀 JSON 檔案或 PostgreSQL（見 phase3_5 設計文件第 2 節）。

    `source` 可明確指定覆蓋 DATA_SOURCE（供 scripts/compare_data_sources.py 兩邊比對使用），一般呼叫端不需傳入。

    `kind='index'`：讀取大盤指數而非個股（見大盤指數功能規劃書 ADR-I2）。只影響 JSON 路徑解析
    （改讀 data/{market}/_indices/{code}.json），PostgreSQL 分支邏輯完全不變 —— daily_stock_data
    以 symbol 為鍵、指數與個股同表（規劃書 ADR-I1），不需要（也不應該）為此新增
    get_data_source() 的分支。
    """
    if (source or get_data_source()) != "postgres":
        if kind == "index":
            from services.index_fetcher import load_index_json
            return load_index_json(stock_id, market)
        return load_stock_json(stock_id, market)

    repo = StockRepository()
    rows = await repo.get_daily_data(stock_id)
    if not rows:
        return {}

    symbol_info = await repo.get_symbol(stock_id)
    name = symbol_info["name"] if symbol_info else None

    result: Dict[str, Any] = {}
    for row in rows:
        record = daily_row_to_record(row)
        if name:
            record["name"] = name
        if market == "us":
            record["symbol"] = stock_id
        result[row["trade_date"].isoformat()] = record
    return result

async def _discover_stocks_db(market: str, tracked_codes: set) -> List[Dict[str, Any]]:
    """discover_available_stocks() 的 PostgreSQL 分支：見 StockRepository.get_symbol_summaries() 註解，
    改用單一批次查詢取代逐 symbol 呼叫 load_stock_data() 的 N+1 寫法。"""
    summaries = await StockRepository().get_symbol_summaries(market)
    return [
        {
            "stock_id": s["symbol"],
            "stock_name": s["name"] or s["symbol"],
            "market": market,
            "latest_date": s["latest_date"].isoformat(),
            "latest_close": s["latest_close"],
            "total_records": s["total_records"],
            "is_tracked": s["symbol"] in tracked_codes
        }
        for s in summaries
    ]

async def discover_available_stocks() -> List[Dict[str, Any]]:
    """回傳系統中所有可用的股票清單與元資料（依 DATA_SOURCE 讀取 JSON 檔案或 PostgreSQL）。"""
    stocks = []

    for market in get_enabled_markets():
        tracked_codes = set(get_target_stocks(market=market))

        if get_data_source() == "postgres":
            stocks.extend(await _discover_stocks_db(market, tracked_codes))
            continue

        stock_ids = _list_stock_ids_json(os.path.join(DATA_DIR, market))
        for stock_id in stock_ids:
            try:
                data = await load_stock_data(stock_id, market)
                if not data:
                    continue

                sorted_dates = sorted(data.keys())
                latest_date = sorted_dates[-1]
                latest_record = data[latest_date]
                # 最新一天常常只回補到行情、三大法人資料尚未到齊（見 aggregate_stock_data 附近註解），
                # 此時當天記錄不會有 name 欄位；往前找最近一筆有 name 的記錄，避免清單顯示代號取代公司名稱。
                stock_name = next(
                    (data[d]["name"] for d in reversed(sorted_dates) if data[d].get("name")),
                    stock_id,
                )
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

async def get_heatmap_data(period: str = "daily", market: Optional[str] = None) -> List[Dict[str, Any]]:
    """回傳供熱力圖使用的資料（包含最新報價、漲跌與 Sparkline），依 DATA_SOURCE 讀取 JSON 或 PostgreSQL。"""
    stocks = []

    enabled_markets = [market] if market and market in get_enabled_markets() else get_enabled_markets()
    for m in enabled_markets:
        tracked_codes = set(get_target_stocks(market=m))
        if not tracked_codes:
            continue

        if get_data_source() == "postgres":
            stock_ids = await _list_stock_ids_db(m)
        else:
            stock_ids = _list_stock_ids_json(os.path.join(DATA_DIR, m))

        for stock_id in stock_ids:
            if stock_id not in tracked_codes:
                continue

            try:
                data = await load_stock_data(stock_id, m)
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

        for f in PRICE_END_FIELDS:
            valid_vals = [r[f] for r in records if f in r and r[f] is not None and r[f] > 0]
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

async def get_stock_chart_payload(stock_id: str, period: str = "daily", months: int = 3, market: str = "tw",
                                   source: Optional[str] = None, kind: str = "stock") -> Dict[str, Any]:
    raw_data = await load_stock_data(stock_id, market, source=source, kind=kind)
    if not raw_data:
        label = "指數" if kind == "index" else "股票"
        return {"error": f"找不到{label} {stock_id} 的數據資料"}

    aggregated_records = aggregate_stock_data(raw_data, period=period, months=months)
    if not aggregated_records:
        return {"error": "指定時間範圍內無數據"}

    dates = [r["date"] for r in aggregated_records]
    stock_name = aggregated_records[0].get("name", stock_id)

    # 部分交易日可能只抓到三大法人/融資融券資料、行情尚未回補（或該來源當日查無資料），
    # 此時 open/close 會是預設值 0 ── 若原樣塞進 K 棒，會把 Y 軸座標硬拉到 0，
    # 導致真實價格區間被壓縮成一條線（K 線圖跑掉），tooltip 也會顯示開盤價 0 這種假資料。
    # 改為 None，讓 ECharts 該天直接跳過（留空），不參與座標軸範圍計算。
    kline_data = [
        [r.get("open", 0), r.get("close", 0), r.get("low", 0), r.get("high", 0)]
        if r.get("open", 0) and r.get("close", 0)
        else None
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

    # 均線由後端統一計算，確保策略掃描（strategies/）與前端繪圖使用同一組數值，避免精度不一致
    # （均線策略警示系統 設計文件第 6.1 節設計決策）。0 視為缺值（比照上方 kline_data 的處理）。
    closes_for_ma = [r.get("close") or None for r in aggregated_records]
    moving_averages = compute_ma_set(closes_for_ma, MA_PERIODS)

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
        "moving_averages": moving_averages,
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
