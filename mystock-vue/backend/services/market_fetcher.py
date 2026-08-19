"""全市場每日資料擷取與作業管線服務（選股功能與爬蟲 規格書 §3、§14 P0-3/4）。

負責：
1. 抓取 TWSE 全市場每日收盤行情 (MI_INDEX)、三大法人買賣超 (T86)、融資融券 (MI_MARGN)、個股估值 (BWIBBU)
2. 寫入前先以未知代號自動補入 symbols 代碼主檔（§3.6）
3. 資料品質檢核（§3.7，異常標記 suspect）
4. 支援節流控制、指數退避重試、連續失敗熔斷、中斷續傳（§3.9）與並發防護
5. 排程作業鏈與手動回補
"""
import asyncio
from datetime import date, datetime, timedelta
import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

from config import (
    get_market_fetch_throttle_seconds,
    get_market_manual_backfill_max_days,
    is_market_fetch_enabled,
)
from db.dual_write import dual_write_no_trading_days, log_crawler_run
from repositories.market_repository import ActiveFetchJobError, MarketRepository, _BackgroundSessionFactory, run_async
from services.revenue_market_fetcher import RevenueMarketFetcher
from services.symbol_master_fetcher import sync_tw_symbol_master
from services.valuation_fetcher import ValuationFetcher

logger = logging.getLogger("mystock-backend")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

_MI_MARGN_FIELD_MAP = {
    "margin_buy": 2,          # 融資買進(張)
    "margin_sell": 3,         # 融資賣出(張)
    "margin_redeem": 4,       # 融資現金償還(張)
    "margin_balance": 6,      # 融資餘額(張)
    "margin_quota": 7,        # 融資限額(張)（若有的話）
    "short_buy": 8,           # 融券買進(張)
    "short_sell": 9,          # 融券賣出(張)
    "short_redeem": 10,       # 融券現券償還(張)
    "short_balance": 12,      # 融券餘額(張)
    "offset_amount": 14,      # 資券互抵(張)
}


def _clean_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    s = str(val).strip().replace(",", "")
    if not s or s in ("-", "--", "N/A", "null", "None"):
        return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def _clean_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    s = str(val).strip().replace(",", "")
    if not s or s in ("-", "--", "N/A", "null", "None"):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _is_foreign_excl_net(f: str) -> bool:
    return "買賣超" in f and ("外陸資" in f or (f.startswith("外資") and "自營商" not in f))


def _is_foreign_dealer_net(f: str) -> bool:
    return "買賣超" in f and "外資自營商" in f


def _is_trust_net(f: str) -> bool:
    return "買賣超" in f and "投信" in f


def _is_dealer_total_net(f: str) -> bool:
    return (
        "買賣超" in f and "自營商" in f
        and "外資" not in f and "自行買賣" not in f and "避險" not in f
    )


def _is_institutional_net(f: str) -> bool:
    return "買賣超" in f and "三大法人" in f


_T86_FIELD_RULES = [
    ("foreign_excl_idx", _is_foreign_excl_net),
    ("foreign_dealer_idx", _is_foreign_dealer_net),
    ("trust_idx", _is_trust_net),
    ("dealer_idx", _is_dealer_total_net),
    ("institutional_idx", _is_institutional_net),
]


def _locate_t86_columns(fields: list) -> Optional[dict]:
    if not fields:
        return None
    located: dict = {}
    used: set = set()
    for key, match in _T86_FIELD_RULES:
        idx = next((i for i, f in enumerate(fields) if match(f) and i not in used), None)
        if idx is None:
            return None
        located[key] = idx
        used.add(idx)
    return located


class MarketFetcher:
    def __init__(self, throttle_seconds: Optional[int] = None):
        self.throttle_seconds = throttle_seconds if throttle_seconds is not None else get_market_fetch_throttle_seconds()
        # 這裡的方法都是透過 run_async()（背景執行緒）呼叫，不能用 db/session.py 的主 loop
        # 全域單例（會跟 FastAPI 主 event loop 併發的其他請求互相弄壞連線，見
        # market_repository.py run_async() 的說明），改用獨立的背景專用連線池。
        self.repo = MarketRepository(session_factory=_BackgroundSessionFactory())
        self.valuation_fetcher = ValuationFetcher(throttle_seconds=self.throttle_seconds)
        self.revenue_fetcher = RevenueMarketFetcher()
        self._cancel_requested = False
        self._lock = threading.Lock()
        # 目前這個行程內真的有工作執行緒在跑的 job id。DB 裡的 status='running' 只代表「有人開過
        # 這筆作業」，行程重啟或工作執行緒異常結束都會留下孤兒紀錄；要判斷作業是否真的還活著，
        # 必須看這個行程內的狀態，不能只信 DB。
        self._active_job_id: Optional[int] = None

    @property
    def active_job_id(self) -> Optional[int]:
        with self._lock:
            return self._active_job_id

    def _set_active_job(self, job_id: Optional[int]) -> None:
        with self._lock:
            self._active_job_id = job_id

    def request_cancel(self):
        """設定取消旗標，於當前 target 完成後乾淨結束（§3.9.5）。"""
        self._cancel_requested = True
        logger.info("[MarketFetcher] 收到取消請求，將在目前的抓取單元完成後中止")

    # ── 1. 抓取 TWSE 全市場收盤行情 ───────────────────────────────────
    def fetch_twse_quotes(self, trade_date: date) -> Tuple[List[Dict[str, Any]], bool]:
        """回傳 (records, is_holiday)"""
        date_str = trade_date.strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date_str}&type=ALLBUT0999&response=json"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                logger.warning(f"[MarketFetcher] TWSE MI_INDEX HTTP {r.status_code} ({date_str})")
                return [], False

            data = r.json()
            stat = data.get("stat", "")
            if stat != "OK":
                if "非交易日" in stat or "查無" in stat:
                    return [], True
                return [], False

            # 定位報價表格
            tables = data.get("tables", [])
            quote_table = None
            for t in tables:
                title = t.get("title", "")
                if "每日收盤行情" in title or "價格資訊" in title or len(t.get("data", [])) > 500:
                    quote_table = t
                    break
            if not quote_table and "data9" in data:
                quote_table = {"fields": data.get("fields9", []), "data": data.get("data9", [])}

            if not quote_table:
                return [], False

            fields = quote_table.get("fields", [])
            raw_data = quote_table.get("data", [])
            if not raw_data:
                return [], False

            # 欄位索引尋找
            # 典型順序: 0證券代號, 1證券名稱, 2成交股數, 3成交筆數, 4成交金額, 5開盤價, 6最高價, 7最低價, 8收盤價, 9漲跌(+/-), 10漲跌價差, 11最後揭示買價...
            col_map = {}
            for i, f in enumerate(fields):
                if "證券代號" in f: col_map["symbol"] = i
                elif "證券名稱" in f: col_map["name"] = i
                elif "成交股數" in f: col_map["volume"] = i
                elif "成交筆數" in f: col_map["trades"] = i
                elif "成交金額" in f: col_map["turnover"] = i
                elif "開盤價" in f: col_map["open"] = i
                elif "最高價" in f: col_map["high"] = i
                elif "最低價" in f: col_map["low"] = i
                elif "收盤價" in f: col_map["close"] = i
                elif "漲跌價差" in f: col_map["change"] = i
                elif "漲跌(+/-)" in f: col_map["sign"] = i

            records = []
            symbols_meta = []
            for row in raw_data:
                sym_idx = col_map.get("symbol", 0)
                if len(row) <= sym_idx:
                    continue
                symbol = str(row[sym_idx]).strip()
                name = str(row[col_map.get("name", 1)]).strip() if "name" in col_map else symbol
                if not symbol:
                    continue

                open_p = _clean_float(row[col_map["open"]]) if "open" in col_map else None
                high_p = _clean_float(row[col_map["high"]]) if "high" in col_map else None
                low_p = _clean_float(row[col_map["low"]]) if "low" in col_map else None
                close_p = _clean_float(row[col_map["close"]]) if "close" in col_map else None
                vol = _clean_int(row[col_map["volume"]]) if "volume" in col_map else None
                turnover = _clean_int(row[col_map["turnover"]]) if "turnover" in col_map else None
                trades = _clean_int(row[col_map["trades"]]) if "trades" in col_map else None
                change = _clean_float(row[col_map["change"]]) if "change" in col_map else None

                # 處理正負號
                if change is not None and "sign" in col_map:
                    sign_val = str(row[col_map["sign"]])
                    if "-" in sign_val:
                        change = -abs(change)
                    elif "+" in sign_val:
                        change = abs(change)

                # 計算漲跌幅
                change_pct = None
                if close_p is not None and change is not None:
                    prev_close = close_p - change
                    if prev_close > 0:
                        change_pct = round((change / prev_close) * 100, 4)

                # 品質檢核 (§3.7)
                quality = "ok"
                if (close_p is not None and close_p <= 0) or (high_p and low_p and high_p < low_p) or (vol is not None and vol < 0):
                    quality = "suspect"

                records.append({
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "market_type": "tw",
                    "exchange": "TWSE",
                    "open_price": open_p,
                    "high_price": high_p,
                    "low_price": low_p,
                    "close_price": close_p,
                    "change_amount": change,
                    "change_percent": change_pct,
                    "volume": vol,
                    "turnover": turnover,
                    "transaction_count": trades,
                    "data_quality": quality,
                    "source": "MI_INDEX",
                })
                symbols_meta.append({"symbol": symbol, "name": name, "exchange": "TWSE"})

            # 寫入前先確保 symbols 主檔存在（§3.6）
            run_async(self.repo.ensure_symbols_exist(symbols_meta, "tw"))
            return records, False
        except Exception as e:
            logger.error(f"[MarketFetcher] 抓取 TWSE 行情失敗 ({date_str}): {e}")
            return [], False

    # ── 2. 抓取 TWSE 全市場三大法人與融資融券 ─────────────────────────
    def fetch_twse_chips(self, trade_date: date) -> Tuple[List[Dict[str, Any]], bool]:
        date_str = trade_date.strftime("%Y%m%d")
        # T86 必須用 ALLBUT0999（不含權證、牛熊證、可展延牛熊證），跟行情 MI_INDEX 取的範圍一致。
        # 用 selectType=ALL 會一次帶回 1.5 萬筆、其中 1.4 萬筆是權證代號，這些代號不在 symbols
        # 主檔裡，落地時整批 UPSERT 會撞 FK 而讓回補作業從中間斷掉（實際發生過）。
        t86_url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALLBUT0999&response=json"
        margn_url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date_str}&selectType=ALL&response=json"

        # 1. 抓取 T86 法人買賣超
        t86_by_sym: Dict[str, dict] = {}
        try:
            r = requests.get(t86_url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                res = r.json()
                if res.get("stat") == "OK":
                    columns = _locate_t86_columns(res.get("fields", []))
                    if columns:
                        for row in res.get("data", []):
                            sym = str(row[0]).strip()
                            if not sym:
                                continue
                            try:
                                f_excl = _clean_int(row[columns["foreign_excl_idx"]]) or 0
                                f_dealer = _clean_int(row[columns["foreign_dealer_idx"]]) or 0
                                f_net = f_excl + f_dealer
                                t_net = _clean_int(row[columns["trust_idx"]]) or 0
                                d_net = _clean_int(row[columns["dealer_idx"]]) or 0
                                inst_net = _clean_int(row[columns["institutional_idx"]]) or 0

                                # 檢核合計是否一致
                                quality = "ok"
                                if f_net + t_net + d_net != inst_net:
                                    quality = "suspect"

                                t86_by_sym[sym] = {
                                    "foreign_net": f_net,
                                    "trust_net": t_net,
                                    "dealer_net": d_net,
                                    "institutional_net": inst_net,
                                    "data_quality": quality,
                                }
                            except (ValueError, IndexError):
                                pass
                elif "非交易日" in res.get("stat", "") or "查無" in res.get("stat", ""):
                    return [], True
        except Exception as e:
            logger.warning(f"[MarketFetcher] T86 抓取失敗 ({date_str}): {e}")

        time.sleep(self.throttle_seconds)

        # 2. 抓取 MI_MARGN 融資融券
        margin_by_sym: Dict[str, dict] = {}
        try:
            r = requests.get(margn_url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                res = r.json()
                if res.get("stat") == "OK":
                    tables = res.get("tables", [])
                    stock_rows = tables[1].get("data", []) if len(tables) > 1 else []
                    for row in stock_rows:
                        sym = str(row[0]).strip()
                        if not sym:
                            continue
                        try:
                            margin_by_sym[sym] = {
                                "margin_buy": _clean_int(row[2]),
                                "margin_sell": _clean_int(row[3]),
                                "margin_redeem": _clean_int(row[4]),
                                "margin_balance": _clean_int(row[6]),
                                "short_buy": _clean_int(row[8]),
                                "short_sell": _clean_int(row[9]),
                                "short_redeem": _clean_int(row[10]),
                                "short_balance": _clean_int(row[12]),
                                "offset_amount": _clean_int(row[14]) if len(row) > 14 else None,
                            }
                        except (ValueError, IndexError):
                            pass
        except Exception as e:
            logger.warning(f"[MarketFetcher] MI_MARGN 抓取失敗 ({date_str}): {e}")

        # 3. 合併結果
        all_symbols = set(t86_by_sym.keys()).union(set(margin_by_sym.keys()))
        records = []
        for sym in all_symbols:
            t86_info = t86_by_sym.get(sym, {})
            m_info = margin_by_sym.get(sym, {})
            records.append({
                "symbol": sym,
                "trade_date": trade_date,
                "market_type": "tw",
                "exchange": "TWSE",
                "foreign_net": t86_info.get("foreign_net"),
                "trust_net": t86_info.get("trust_net"),
                "dealer_net": t86_info.get("dealer_net"),
                "institutional_net": t86_info.get("institutional_net"),
                "margin_balance": m_info.get("margin_balance"),
                "margin_buy": m_info.get("margin_buy"),
                "margin_sell": m_info.get("margin_sell"),
                "margin_redeem": m_info.get("margin_redeem"),
                "margin_quota": None,
                "short_balance": m_info.get("short_balance"),
                "short_buy": m_info.get("short_buy"),
                "short_sell": m_info.get("short_sell"),
                "short_redeem": m_info.get("short_redeem"),
                "offset_amount": m_info.get("offset_amount"),
                "data_quality": t86_info.get("data_quality", "ok"),
                "source": "T86+MI_MARGN",
            })

        return records, False

    # ── 3. 單日作業單元執行（Atomic Unit: 交易日 × Targets）───────────
    def _drop_unknown_symbols(self, records: List[Dict[str, Any]], label: str, date_str: str) -> List[Dict[str, Any]]:
        """濾掉 symbols 主檔沒有的代號再落地。

        daily_market_chip / daily_valuation 都有 symbol -> symbols 的 FK（ON DELETE RESTRICT），
        來源多帶了一檔主檔沒有的代號，整批 UPSERT 就會拋 IntegrityError 讓整個回補作業從中間
        斷掉。寧可少寫幾檔並留下警告，也不要讓一檔雜訊代號炸掉整批。"""
        if not records:
            return records
        symbols = [r["symbol"] for r in records]
        known = run_async(self.repo.filter_existing_symbols(symbols))
        kept = [r for r in records if r["symbol"] in known]
        dropped = len(records) - len(kept)
        if dropped:
            unknown = sorted({s for s in symbols if s not in known})
            logger.warning(
                f"[MarketFetcher] {date_str} {label} 有 {dropped} 筆代號不在代碼主檔中，已略過: {unknown[:10]}"
            )
        return kept

    def fetch_day_market(self, trade_date: date, targets: List[str]) -> Dict[str, Any]:
        """單一交易日抓取與落地，失敗自動退避重試（3次）。
        回傳 {"success": bool, "is_holiday": bool, "counts": {target: 落地筆數}}，
        供呼叫端組裝 crawler_logs 的實際成功筆數（不得用假數字，見設計文件 §3.3）。"""
        date_str = trade_date.strftime("%Y-%m-%d")
        logger.info(f"[MarketFetcher] ── 開始抓取交易日 {date_str} (targets={targets}) ──")
        result: Dict[str, Any] = {"success": True, "is_holiday": False, "counts": {}}

        # 1. 抓取行情 (Quotes)
        if "quote" in targets:
            quotes, is_holiday = self._retry_fetch(lambda: self.fetch_twse_quotes(trade_date), default=([], False))
            if is_holiday:
                logger.info(f"[MarketFetcher] {date_str} 為休市日，記錄至 market_no_trading_days")
                dual_write_no_trading_days("tw", [date_str], source="probed")
                result["is_holiday"] = True
                return result

            if not quotes:
                logger.warning(f"[MarketFetcher] {date_str} 行情資料抓取失敗或為空")
                result["success"] = False
                return result

            count = run_async(self.repo.upsert_quotes(quotes))
            result["counts"]["quote"] = count
            logger.info(f"[MarketFetcher] {date_str} 行情落地完成，共 {count} 筆")
            time.sleep(self.throttle_seconds)

        # 2. 抓取籌碼 (Chips)
        # 每個 target 前都檢查取消旗標：單日三個 target 加上節流／重試動輒好幾分鐘，只在「換日」
        # 時才看旗標的話，使用者按下取消後會很久都沒反應（前端就是卡在這裡）。各 target 的落地
        # 本身是獨立交易，中途停在 target 邊界仍是乾淨狀態，缺的部分下次由 missing_dates() 補回。
        if "chip" in targets and not self._cancel_requested:
            chips, _ = self._retry_fetch(lambda: self.fetch_twse_chips(trade_date), default=([], False))
            chips = self._drop_unknown_symbols(chips, "籌碼", date_str)
            if chips:
                count = run_async(self.repo.upsert_chips(chips))
                result["counts"]["chip"] = count
                logger.info(f"[MarketFetcher] {date_str} 籌碼落地完成，共 {count} 筆")
            time.sleep(self.throttle_seconds)

        # 3. 抓取估值 (Valuation)
        if "valuation" in targets and not self._cancel_requested:
            val_records = self._retry_fetch(lambda: self.valuation_fetcher.fetch_twse_valuation(trade_date), default=[])
            val_records = self._drop_unknown_symbols(val_records, "估值", date_str)
            if val_records:
                count = run_async(self.repo.upsert_valuation(val_records))
                result["counts"]["valuation"] = count
                logger.info(f"[MarketFetcher] {date_str} 估值落地完成，共 {count} 筆")
            time.sleep(self.throttle_seconds)

        return result

    def _retry_fetch(self, func_to_run, max_retries: int = 3, default: Any = None) -> Any:
        """指數退避重試（3s -> 9s -> 27s）。

        不可依賴回傳值本身的 truthiness 判斷是否成功——`fetch_twse_quotes`/`fetch_twse_chips`
        內部已自行 catch 例外並回傳 `([], False)` 這種 2 元素 tuple，任何非空 tuple 恆為
        truthy，會讓「內部已判定失敗」的空結果被誤判為成功、完全不會重試。這裡改成明確檢查
        payload（tuple 取第一個元素、否則直接檢查該值）是否非空。
        重試耗盡後直接回傳最後一次實際取得的結果，不再多打一次請求去猜回傳型別。"""
        last_result = default
        for attempt in range(1, max_retries + 1):
            try:
                last_result = func_to_run()
            except Exception as e:
                logger.warning(f"[MarketFetcher] 執行失敗 (第 {attempt} 次): {e}")
                last_result = default
            else:
                payload = last_result[0] if isinstance(last_result, tuple) else last_result
                if payload:
                    return last_result

            if attempt < max_retries:
                backoff = self.throttle_seconds * (3 ** (attempt - 1))
                logger.info(f"[MarketFetcher] 第 {attempt} 次嘗試無有效資料，{backoff}s 後重試")
                time.sleep(backoff)
        return last_result

    # ── 4. 每日排程管線（Daily Pipeline，§3.3）───────────────────────
    def run_daily_pipeline(self, trade_date: Optional[date] = None, targets: Optional[List[str]] = None) -> dict:
        """每日作業鏈：代碼主檔同步 -> 行情 -> 籌碼 -> 估值。"""
        if not is_market_fetch_enabled():
            logger.info("[MarketFetcher] MARKET_FETCH_ENABLED 為 False，略過全市場排程")
            return {"status": "skipped"}

        t_date = trade_date or date.today()
        # 若為週末直接略過
        if t_date.weekday() >= 5:
            logger.info(f"[MarketFetcher] {t_date} 為週末，略過抓取")
            return {"status": "weekend"}

        targets = targets or ["quote", "chip", "valuation"]
        try:
            job_id = run_async(
                self.repo.create_fetch_job(
                    scope="daily",
                    targets=",".join(targets),
                    start_date=t_date,
                    end_date=t_date,
                    total_days=1,
                    trigger_type="schedule",
                )
            )
        except ActiveFetchJobError as e:
            logger.warning(f"[MarketFetcher] {e}，本次每日排程略過")
            return {"status": "already_running"}

        self._set_active_job(job_id)
        started_at = datetime.now()
        success = False
        try:
            # 1. 代碼主檔每日同步（§3.3 步驟 1）
            try:
                sync_tw_symbol_master()
            except Exception as e:
                logger.warning(f"[MarketFetcher] 代碼主檔同步異常: {e}")

            # 2. 執行全市場每日抓取
            fetch_result = self.fetch_day_market(t_date, targets)
            success = fetch_result["success"] or fetch_result["is_holiday"]
            status_str = "completed" if success else "failed"
            run_async(self.repo.complete_fetch_job(job_id, status_str))
            total_written = sum(fetch_result["counts"].values())
            log_crawler_run(
                market_type="tw",
                trigger_type="schedule",
                started_at=started_at,
                finished_at=datetime.now(),
                status="success" if success else "failed",
                # 全市場批次沒有逐檔成功/失敗的追蹤粒度，symbols_success 以實際落地列數為準
                # （不同 target 落地筆數可能不同，取總和），symbols_failed 僅在整批失敗時標記為 1。
                symbols_success=total_written,
                symbols_failed=0 if success else 1,
                error_message=None if success else "每日抓取失敗",
            )
            return {"status": status_str, "date": str(t_date), "counts": fetch_result["counts"]}
        except Exception as e:
            logger.exception(f"[MarketFetcher] 每日作業鏈例外: {e}")
            run_async(self.repo.complete_fetch_job(job_id, "failed", str(e)[:500]))
            return {"status": "error", "error": str(e)}
        finally:
            self._set_active_job(None)

    # ── 4b. 全市場月營收抓取（§3.2 M、§3.3）───────────────────────────
    def fetch_revenue_now(self, trigger_type: str = "manual") -> Dict[str, Any]:
        """抓取 TWSE 最新一批全市場月營收並落地 monthly_revenue（選股/多因子共振精選依賴此表）。

        月營收是「最新一批快照」而非逐日資料，不比照 fetch_day_market() 走逐日回補管線；
        原本只掛在 scheduler.py 的每月 11 號排程，未上線前／排程失敗後只能等下個月，
        這裡補上可重入的手動觸發路徑（market.py 的 /fetch/revenue）。
        必須用 self.repo（背景專用連線池）呼叫 run_async()，直接 new 一個
        MarketRepository() 會沿用主 loop 的全域 engine，被 run_async() 的新事件迴圈把連線
        綁死後弄壞 FastAPI 主 loop（見 market_repository.py run_async() 的說明）。"""
        logger.info(f"[MarketFetcher] 開始抓取全市場最新月營收 (trigger={trigger_type})...")
        records = self.revenue_fetcher.fetch_twse_monthly_revenue()
        if not records:
            logger.warning("[MarketFetcher] 月營收抓取無資料")
            return {"success": False, "count": 0}
        count = run_async(self.repo.upsert_revenue(records))
        logger.info(f"[MarketFetcher] 月營收抓取完成，共寫入 {count} 筆")
        return {"success": True, "count": count}

    # ── 5. 批次回補與中斷續傳（Backfill & Resume，§3.8、§3.9）────────
    def backfill_market(
        self,
        start_date: date,
        end_date: date,
        targets: Optional[List[str]] = None,
        throttle_seconds: Optional[int] = None,
        trigger_type: str = "manual",
    ) -> dict:
        """批量回補與續傳：以資料為準重算 missing_dates()，單日交易寫入。"""
        if throttle_seconds is not None:
            self.throttle_seconds = throttle_seconds

        targets = targets or ["quote", "chip", "valuation"]
        self._cancel_requested = False

        # 1. 查詢缺日清單
        missing_dates = set()
        for t in targets:
            missing_dates.update(run_async(self.repo.get_missing_dates(t, start_date, end_date, "tw")))
        sorted_missing = sorted(list(missing_dates))
        total_days = len(sorted_missing)

        if total_days == 0:
            logger.info(f"[MarketFetcher] 區間 {start_date} ~ {end_date} 資料已完整，無須補抓")
            return {"status": "completed", "total_days": 0, "done_days": 0}

        try:
            job_id = run_async(
                self.repo.create_fetch_job(
                    scope="backfill",
                    targets=",".join(targets),
                    start_date=start_date,
                    end_date=end_date,
                    total_days=total_days,
                    trigger_type=trigger_type,
                )
            )
        except ActiveFetchJobError as e:
            logger.warning(f"[MarketFetcher] {e}，本次回補請求已略過")
            return {"status": "already_running"}

        self._set_active_job(job_id)
        done_count = 0
        failed_count = 0
        consecutive_failures = 0
        final_status = "completed"
        final_error: Optional[str] = None

        logger.info(f"[MarketFetcher] 開始批量回補：共缺 {total_days} 個交易日 ({start_date} ~ {end_date})")

        # 整個迴圈必須包在 try/finally 裡：任何一步拋出例外（例如整批 UPSERT 撞到 FK）而沒有寫回
        # 終態的話，這筆紀錄會永遠停在 status='running'——前端的進度卡會一直顯示「進行中」且按取消
        # 也沒用，V10 的部分唯一索引更會讓之後所有作業（含每日排程）都建不起來。
        try:
            for d in sorted_missing:
                if self._cancel_requested:
                    logger.info("[MarketFetcher] 使用者主動取消，停止後續回補作業")
                    final_status = "interrupted"
                    final_error = "使用者主動取消"
                    break

                ok = self.fetch_day_market(d, targets)
                if ok["success"] or ok["is_holiday"]:
                    done_count += 1
                    consecutive_failures = 0
                else:
                    failed_count += 1
                    consecutive_failures += 1

                run_async(
                    self.repo.update_job_progress(
                        job_id=job_id,
                        cursor_date=d,
                        done_days=done_count,
                        failed_days=failed_count,
                    )
                )

                # 連續 5 天失敗觸發熔斷（§3.9.5）
                if consecutive_failures >= 5:
                    logger.error("[MarketFetcher] 連續 5 天抓取失敗，疑似遭來源限流，觸發熔斷保護中止作業")
                    final_status = "interrupted"
                    final_error = "連續5天失敗觸發熔斷"
                    break
            else:
                final_status = "completed" if failed_count == 0 else "completed_with_errors"
        except Exception as e:
            logger.exception(f"[MarketFetcher] 批量回補發生未預期例外，作業中止: {e}")
            final_status = "failed"
            final_error = str(e)[:500]
        finally:
            try:
                run_async(self.repo.complete_fetch_job(job_id, final_status, final_error))
            except Exception as e:  # 連終態都寫不回去只能記錄，交由服務啟動時的孤兒回收兜底
                logger.error(f"[MarketFetcher] 寫回作業終態失敗 (job_id={job_id}, status={final_status}): {e}")
            self._set_active_job(None)

        logger.info(f"[MarketFetcher] 批量回補結束（{final_status}）：成功 {done_count} 天，失敗 {failed_count} 天")
        result = {"status": final_status, "total_days": total_days, "done_days": done_count, "failed_days": failed_count}
        if final_error:
            result["error"] = final_error
        return result


# 單例物件
market_fetcher = MarketFetcher()
