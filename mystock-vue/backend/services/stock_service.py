import os
import json
import calendar
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from config import DATA_DIR, MAX_HISTORY_MONTHS, get_target_stocks, get_enabled_markets, get_data_source
from services.fetcher import load_stock_json
from db.mapping import daily_row_to_record
from repositories.stock_repository import StockRepository
from indicators.moving_average import compute_ma_set
from indicators.stochastic import stochastic
from indicators.macd import macd
from indicators.rsi import rsi
from indicators.atr import atr
from indicators.bollinger import bollinger_bands
from indicators.levels import rolling_high_low

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
    if not rows and market == "tw" and kind != "index":
        try:
            from repositories.market_repository import MarketRepository
            m_repo = MarketRepository()
            m_rows = await m_repo.get_symbol_daily_series(stock_id)
            if m_rows:
                symbol_info = await repo.get_symbol(stock_id)
                name = symbol_info["name"] if symbol_info else stock_id
                result: Dict[str, Any] = {}
                for r in m_rows:
                    r["name"] = name
                    result[r["date"]] = r
                return result
        except Exception as e:
            logger.warning(f"[stock_service] 全市場資料庫 fallback 查詢失敗 ({stock_id}): {e}")

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

async def get_latest_quote(stock_id: str, market: str = "tw") -> Optional[Dict[str, Any]]:
    """取最新一筆有效收盤價（供個人投資記帳模組 GET /api/v1/portfolio/quotes 批次報價使用）。

    沿用 load_stock_data() 已經處理好的 DATA_SOURCE 分支，這裡不重新判斷 json/postgres；
    收盤價 0 視為當天未回補到行情（見 PRICE_END_FIELDS 註解與 restore_price_from_legacy.py 的歷史成因），
    往前找最近一筆非 0 的收盤價，都是 0（或沒有資料）就回傳 None，由呼叫端標示「待報價」。
    """
    data = await load_stock_data(stock_id, market)
    if not data:
        return None
    for trade_date in sorted(data.keys(), reverse=True):
        record = data[trade_date]
        close = record.get("close")
        if close:
            return {"symbol": stock_id, "market": market, "date": trade_date, "close": close}
    return None


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

def _build_kd_payload(full_records: List[Dict[str, Any]], display_dates: List[str]) -> Dict[str, Any]:
    """KD 副圖資料（KD指標 設計規格書 §6.1／§6.3）。

    在完整歷史（full_records，聚合時 months=MAX_HISTORY_MONTHS）上計算 K/D，再依日期把結果
    切到目前顯示區間（display_dates）——刻意不用 full_records 前 len(display_dates) 筆這種
    位置切法，是因為非交易日／缺值會讓筆數與日期範圍對不齊，必須以日期本身比對才準確。
    這樣同一天的 K/D 值不會因為使用者選 1 個月或 1 年而不同，也才會跟策略引擎（scanner.py，
    同樣用 MAX_HISTORY_MONTHS 全歷史計算）算出的數字一致。

    刻意不比照套用在 moving_averages（見下方呼叫端註解、KD指標 設計規格書 §12 決議 D5）：
    MA 若資料不足只會誠實斷線（None），KD 若不做這層切片則會算出「看起來正常但其實錯誤」
    的數字，兩者錯誤等級不同，只有 KD 需要這道全歷史切片。
    """
    # 延遲匯入：strategies 套件的 __init__ 會匯入 conditions_tech -> services.chip_provider ->
    # services.stock_service，若在檔案頂層 import 會形成循環匯入（本函式所在的模組正是被匯入的
    # 那一個）。等到實際呼叫時（伺服器啟動流程早已把 strategies 套件匯入完畢）才 import 即可
    # 避開這個問題，同樣手法見 notify/events.py 既有的 _get_strategy_category()。
    from strategies.config_loader import load_strategy_config

    cfg = load_strategy_config()
    kd_params_list = cfg.defaults.get("kd_params") or [[9, 3, 3]]
    params = tuple(kd_params_list[0])
    warmup_bars = cfg.defaults.get("kd_warmup_bars", 25)
    smoothing = cfg.defaults.get("kd_smoothing", "wilder_1_3")

    # 超買／超賣門檻取自 KD 策略設定，讓「YAML 改門檻 → 圖上基準線跟著動」
    # （策略管理架構 設計文件第 9 節「不寫死參數」）；策略未設定或找不到時退回預設 80/20。
    oversold, overbought = 20, 80
    kd_strategy = cfg.get("kd_oversold_golden_cross")
    if kd_strategy:
        kd_cond = next((c for c in kd_strategy.conditions if c.get("type") == "kd_cross"), None)
        if kd_cond:
            oversold = kd_cond.get("oversold_threshold", oversold)
            overbought = kd_cond.get("overbought_threshold", overbought)

    highs = [r.get("high") or None for r in full_records]
    lows = [r.get("low") or None for r in full_records]
    closes = [r.get("close") or None for r in full_records]
    k_full, d_full = stochastic(highs, lows, closes, *params, warmup_bars=warmup_bars, smoothing=smoothing)

    index_by_date = {r["date"]: i for i, r in enumerate(full_records)}
    k_sliced = [k_full[index_by_date[d]] if d in index_by_date else None for d in display_dates]
    d_sliced = [d_full[index_by_date[d]] if d in index_by_date else None for d in display_dates]

    return {
        "params": list(params),
        "smoothing": smoothing,
        "k": k_sliced,
        "d": d_sliced,
        "overbought": overbought,
        "oversold": oversold,
    }


def _build_recursive_indicator_payloads(full_records: List[Dict[str, Any]], display_dates: List[str]) -> Dict[str, Any]:
    """MACD／RSI／ATR（Phase1-基礎量化與技術面 設計文件 FR-P1-7）。

    這三者跟 KD 一樣是「遞迴型」指標，必須在完整歷史（full_records，聚合時
    months=MAX_HISTORY_MONTHS）上算完再依日期切到目前顯示區間，作法完全比照
    _build_kd_payload()（KD指標 設計規格書 §12 決議 D5 的延伸，見該文件 §3.3）：若比照 MA
    在截斷視窗上計算，會產出「看似正常但其實錯誤」的數字——同一天的值不能因為使用者選
    1 個月或 1 年而不同（AC-P1-4）。
    """
    from strategies.config_loader import load_strategy_config

    cfg = load_strategy_config()
    fast, slow, signal_period = cfg.defaults.get("macd_params") or [12, 26, 9]
    rsi_periods = cfg.defaults.get("rsi_periods") or [6, 14]
    atr_period = cfg.defaults.get("atr_period", 14)

    highs = [r.get("high") or None for r in full_records]
    lows = [r.get("low") or None for r in full_records]
    closes = [r.get("close") or None for r in full_records]

    index_by_date = {r["date"]: i for i, r in enumerate(full_records)}

    def _slice(series: List[Optional[float]]) -> List[Optional[float]]:
        return [series[index_by_date[d]] if d in index_by_date else None for d in display_dates]

    dif, signal, histogram = macd(closes, fast, slow, signal_period)
    macd_payload = {
        "params": [fast, slow, signal_period],
        "dif": _slice(dif),
        "signal": _slice(signal),
        "histogram": _slice(histogram),
    }

    # RSI 超買／超賣門檻取自策略設定，讓「YAML 改門檻 → 圖上基準線跟著動」（比照
    # _build_kd_payload() 對 KD 門檻的既有作法，Phase1-基礎量化與技術面 設計文件 §9 Q-1）；
    # 找不到對應策略時退回業界慣用 70/30（Q-3 決議，非 v1.0 草案的 80/20）。
    rsi_oversold, rsi_overbought = 30, 70
    rsi_strategy = cfg.get("rsi_oversold_recovery")
    if rsi_strategy:
        rsi_cond = next((c for c in rsi_strategy.conditions if c.get("type") == "rsi_zone"), None)
        if rsi_cond:
            rsi_oversold = rsi_cond.get("oversold_threshold", rsi_oversold)
            rsi_overbought = rsi_cond.get("overbought_threshold", rsi_overbought)

    rsi_payload: Dict[str, Any] = {
        "periods": list(rsi_periods),
        "oversold": rsi_oversold,
        "overbought": rsi_overbought,
    }
    for p in rsi_periods:
        rsi_payload[f"rsi_{p}"] = _slice(rsi(closes, p))

    atr_payload = {
        "period": atr_period,
        f"atr_{atr_period}": _slice(atr(highs, lows, closes, atr_period)),
    }

    return {"macd": macd_payload, "rsi": rsi_payload, "atr": atr_payload}


def _build_bollinger_and_levels_payload(
    closes_for_ma: List[Optional[float]],
    moving_averages: Dict[str, List[Optional[float]]],
    aggregated_records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """布林通道與近 N 日高低（Phase1-基礎量化與技術面 設計文件 FR-P1-7）。

    這兩者是「視窗型」指標，比照 MA 在目前顯示區間（截斷後）上直接計算即可，資料不足只會
    誠實斷線，不需要像 MACD／RSI／ATR／KD 那樣做全歷史切片（ADR-P1-04）。
    """
    from strategies.config_loader import load_strategy_config

    cfg = load_strategy_config()
    bollinger_period, bollinger_num_std = cfg.defaults.get("bollinger_params") or [20, 2.0]
    levels_windows = cfg.defaults.get("levels_windows") or [20, 60]

    # 中軌重用既有 SMA 結果，不重算一次（ADR-P1-05）；只有對應天期的 MA 未被納入
    # MA_PERIODS（如改成非既有天期）時，才退回 bollinger_bands() 內部自算 SMA。
    existing_middle = moving_averages.get(f"MA{bollinger_period}")
    upper, middle, lower, bandwidth = bollinger_bands(
        closes_for_ma, bollinger_period, bollinger_num_std, middle=existing_middle
    )
    bollinger_payload = {
        "params": [bollinger_period, bollinger_num_std],
        "upper": upper,
        "middle": middle,
        "lower": lower,
        "bandwidth": bandwidth,
    }

    highs_for_levels = [r.get("high") or None for r in aggregated_records]
    lows_for_levels = [r.get("low") or None for r in aggregated_records]
    levels_payload: Dict[str, Any] = {"windows": list(levels_windows)}
    for w in levels_windows:
        resistance, support = rolling_high_low(highs_for_levels, lows_for_levels, w)
        levels_payload[f"resistance_{w}d"] = resistance
        levels_payload[f"support_{w}d"] = support

    return {"bollinger": bollinger_payload, "levels": levels_payload}


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
    # 注意：這裡是「先依 months 截斷、再計算」，不像下面 KD 是在全歷史上算完才切片
    # （KD指標 設計規格書 §12 決議 D5：MA 資料不足只會誠實斷線，不像 KD 會算出看似正常但
    # 其實錯誤的數字，兩者錯誤等級不同，本次只有 KD 需要全歷史切片，MA 維持現狀）——因此短
    # 區間（如 1 個月）會看不到 MA60／MA240 的線，這是已知限制，不是遺漏。
    closes_for_ma = [r.get("close") or None for r in aggregated_records]
    moving_averages = compute_ma_set(closes_for_ma, MA_PERIODS)

    # KD（KD指標 設計規格書 §6.1／§6.3）：在完整歷史上計算後再依 dates 切片，見 _build_kd_payload()。
    full_records = aggregate_stock_data(raw_data, period=period, months=MAX_HISTORY_MONTHS)
    kd_payload = _build_kd_payload(full_records, dates)

    # MACD／RSI／ATR（遞迴型，全歷史計算後切片）＋ 布林通道／近N日高低（視窗型，截斷後計算）
    # ——見 Phase1-基礎量化與技術面 設計文件 §3.3、FR-P1-7。
    recursive_indicators = _build_recursive_indicator_payloads(full_records, dates)
    bollinger_and_levels = _build_bollinger_and_levels_payload(closes_for_ma, moving_averages, aggregated_records)

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
        "kd": kd_payload,
        "macd": recursive_indicators["macd"],
        "rsi": recursive_indicators["rsi"],
        "atr": recursive_indicators["atr"],
        "bollinger": bollinger_and_levels["bollinger"],
        "levels": bollinger_and_levels["levels"],
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
