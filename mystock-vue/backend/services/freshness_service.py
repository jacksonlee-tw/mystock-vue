"""登入首頁資料新鮮度判斷與自動補抓（見 docs/19.登入自動補抓資料/登入自動補抓資料_規劃書.md §3.3、§3.4）。

三個部分：
1. `build_market_report()`：算出某市場的追蹤個股／指數落後清單（60 秒行程內快取）。
2. `decide_action()`：純函式，依報告＋目前狀態（抓取中／排程時窗／節流紀錄）決定該市場這次
   要 `up_to_date` / `fetch_running` / `schedule_window` / `throttled` / `triggered` 哪一種，
   抽成純函式方便單元測試涵蓋時窗與節流的邊界情境（§3.4 表格）。
3. `catch_up()`：對外唯一入口，把「算報告 → 決策 → 登記節流鍵 → 啟動背景 thread」包在
   模組層 `asyncio.Lock` 內做成原子操作（ADR-03），背景 thread 依序處理各市場的實際補抓。

節流紀錄（`_throttle`）存在行程記憶體，重啟即遺失——代價是最多多補一次，可接受（規劃書 T4）。
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from datetime import time as dt_time
from typing import Optional

import pytz

from config import get_enabled_markets, get_months_range, get_schedule_config
from services.fetcher import fetch_status, run_fetch_process
from services.index_fetcher import get_index_definitions, load_index_json, run_index_fetch_process
from services.trading_calendar import get_latest_expected_trading_date
from services.tracking_service import get_crawl_enabled_symbols
from services.us_fetcher import run_us_fetch_process

logger = logging.getLogger("mystock-backend")

_TW_TZ = pytz.timezone("Asia/Taipei")

# ── 1. 新鮮度報告（§3.3）─────────────────────────────────────────────────

_REPORT_CACHE_TTL_SECONDS = 60
# key: market -> (cached_at_monotonic, report)
_report_cache: dict[str, tuple[float, dict]] = {}
_report_cache_lock = threading.Lock()


def invalidate_report_cache(market: Optional[str] = None) -> None:
    """補抓完成後清掉快取，讓下一次 GET/POST 讀到最新落後狀態（§3.4 步驟 5）。"""
    with _report_cache_lock:
        if market is None:
            _report_cache.clear()
        else:
            _report_cache.pop(market, None)


async def build_market_report(market: str, now: Optional[datetime] = None, *, use_cache: bool = True) -> dict:
    """單一市場的新鮮度報告（§3.3）。多分頁同時開首頁時，60 秒內重複呼叫直接吃快取，
    不重複讀取數十個 JSON 檔。"""
    if use_cache:
        with _report_cache_lock:
            cached = _report_cache.get(market)
        if cached is not None and time.monotonic() - cached[0] < _REPORT_CACHE_TTL_SECONDS:
            return cached[1]

    expected_date = get_latest_expected_trading_date(market, now)
    now_tw = now or datetime.now(_TW_TZ)
    checked_at = (_TW_TZ.localize(now_tw) if now_tw.tzinfo is None else now_tw).isoformat()

    symbols = await get_crawl_enabled_symbols(market)
    stale_stocks: list[dict] = []
    if symbols:
        from repositories.stock_repository import StockRepository

        coverage = await StockRepository().get_coverage_summary(symbols, market)
        for symbol in symbols:
            end_date = coverage.get(symbol, {}).get("end_date")
            # 沒資料的新標的（end_date is None）也算落後——剛加入追蹤清單、背景抓取失敗者一併補（§3.3）
            if end_date is None or end_date < expected_date:
                stale_stocks.append({"symbol": symbol, "last_date": end_date})

    definitions = get_index_definitions(market)
    stale_indices: list[dict] = []
    for definition in definitions:
        data = load_index_json(definition.code, market)
        last_date = max(data.keys()) if data else None
        if last_date is None or last_date < expected_date:
            stale_indices.append({"code": definition.code, "last_date": last_date})

    report = {
        "market": market,
        "expected_date": expected_date,
        "checked_at": checked_at,
        "stocks": {"total": len(symbols), "stale": stale_stocks},
        "indices": {"total": len(definitions), "stale": stale_indices},
        "is_stale": bool(stale_stocks or stale_indices),
    }

    with _report_cache_lock:
        _report_cache[market] = (time.monotonic(), report)
    return report


# ── 2. 補抓決策（純函式，§3.4）────────────────────────────────────────────

# 失敗後允許重試的冷卻秒數（§3.4 條件 5）
RETRY_AFTER_FAILURE_SECONDS = 30 * 60
# 排程時窗：[排程時間 − 10 分, 排程時間 + 90 分]（§3.4 條件 3）
_SCHEDULE_WINDOW_BEFORE_MINUTES = 10
_SCHEDULE_WINDOW_AFTER_MINUTES = 90

# 給人看的中文市場名稱（§3.5：reason 為中文說明），只用於組訊息文字，不影響任何邏輯判斷
_MARKET_LABELS = {"tw": "台股", "us": "美股"}


def _schedule_window(setting: dict, tz_name: str, today: datetime) -> tuple[datetime, datetime]:
    tz = pytz.timezone(tz_name)
    sched = tz.localize(datetime.combine(today.date(), dt_time(setting["hour"], setting["minute"])))
    return (
        sched - timedelta(minutes=_SCHEDULE_WINDOW_BEFORE_MINUTES),
        sched + timedelta(minutes=_SCHEDULE_WINDOW_AFTER_MINUTES),
    )


def decide_action(
    *,
    report: dict,
    is_fetch_running: bool,
    now: datetime,
    schedule_config: dict,
    throttle_state: Optional[dict],
    now_mono: float,
    force: bool = False,
) -> tuple[str, str]:
    """回傳 (action, reason)。`now` 須為排程時區（schedule_config["timezone"]）的 tz-aware
    時間；`now_mono`／`throttle_state["finished_at_mono"]` 用 `time.monotonic()` 量測失敗重試冷卻，
    避開時區／夏令時換算的坑（§3.4 條件 5）。"""
    market = report["market"]
    expected_date = report["expected_date"]

    # 1. 已是最新
    if not report["is_stale"]:
        return "up_to_date", "資料已是最新"

    # 2. 已有抓取任務執行中（排程／手動／另一個補抓）
    if is_fetch_running:
        return "fetch_running", "已有抓取任務正在執行，直接顯示進度"

    stale_count = len(report["stocks"]["stale"]) + len(report["indices"]["stale"])

    if not force:
        # 3. 排程時窗：讓排程自己跑完整鏈，避免補抓佔住 fetch_status 導致排程整個跳過
        setting = schedule_config.get("markets", {}).get(market)
        if setting and setting["enabled"]:
            window_start, window_end = _schedule_window(setting, schedule_config["timezone"], now)
            if window_start <= now <= window_end:
                label = _MARKET_LABELS.get(market, market)
                return "schedule_window", f"{label}排程 {setting['time']} 即將更新資料"

        # 4／5. 節流：同一 (market, expected_date) 成功補抓過就不再重試；失敗允許 30 分後重試
        if throttle_state and throttle_state.get("expected_date") == expected_date:
            status = throttle_state.get("status")
            if status in ("running", "done", "skipped"):
                return "throttled", f"本交易日已補抓過，仍有 {stale_count} 檔無新資料（可能停牌）"
            if status == "failed":
                finished_mono = throttle_state.get("finished_at_mono")
                if finished_mono is not None and now_mono - finished_mono < RETRY_AFTER_FAILURE_SECONDS:
                    return "throttled", "上次補抓失敗，30 分鐘後才會自動重試"

    # 6. 其他：觸發補抓
    return "triggered", "已在背景啟動補抓"


# ── 3. 派工與背景 worker（§3.4）──────────────────────────────────────────

_catchup_lock_holder: dict[str, object] = {}


def _get_catchup_lock():
    """延後建立 asyncio.Lock：模組載入時可能還沒有執行中的 event loop（例如被同步測試 import）。"""
    import asyncio

    lock = _catchup_lock_holder.get("lock")
    if lock is None:
        lock = asyncio.Lock()
        _catchup_lock_holder["lock"] = lock
    return lock


_worker_lock = threading.Lock()
_throttle_lock = threading.Lock()
_throttle: dict[str, dict] = {}

# 背景 worker 依序處理的市場順序，與請求帶入的 markets 順序無關（§3.4：「依序 tw → us」）
_WORKER_MARKET_ORDER = ["tw", "us"]


def _register_throttle(market: str, expected_date: str) -> None:
    with _throttle_lock:
        _throttle[market] = {"expected_date": expected_date, "status": "running", "finished_at_mono": None}


def _mark_throttle(market: str, status: str) -> None:
    with _throttle_lock:
        entry = _throttle.get(market)
        if entry is not None:
            entry["status"] = status
            entry["finished_at_mono"] = time.monotonic()


def get_throttle_state(market: str) -> Optional[dict]:
    with _throttle_lock:
        entry = _throttle.get(market)
        return dict(entry) if entry is not None else None


def _catch_up_worker(markets: list[str], stale_by_market: dict[str, dict]) -> None:
    """背景執行緒（daemon）：依序處理各市場的補抓＋掃描（§3.4）。與 `market_fetcher` 手法一致，
    不用 FastAPI `BackgroundTasks`，避免多市場串接時跟單一請求的生命週期綁在一起。"""
    with _worker_lock:
        for market in markets:
            try:
                if fetch_status.get_snapshot()["is_running"]:
                    logger.info(f"[自動補抓] {market} 開跑前發現已有抓取任務執行中，本次跳過（下次可再試）")
                    _mark_throttle(market, "skipped")
                    continue

                stale = stale_by_market[market]
                stale_index_codes = [i["code"] for i in stale["indices"]]
                stale_stock_symbols = [s["symbol"] for s in stale["stocks"]]
                logger.info(f"[自動補抓] {market} 開始：指數 {stale_index_codes}，個股 {stale_stock_symbols}")

                if stale_index_codes:
                    run_index_fetch_process(
                        market=market, codes=stale_index_codes, mode="incremental", trigger_type="auto_catchup",
                    )
                if stale_stock_symbols:
                    months = get_months_range()
                    fetch_fn = run_us_fetch_process if market == "us" else run_fetch_process
                    fetch_fn(
                        target_stocks=stale_stock_symbols, months=months,
                        mode="incremental", trigger_type="auto_catchup",
                    )

                from services.scheduler import _publish_fetch_result, _scan_after_fetch

                _publish_fetch_result(market)
                _scan_after_fetch(market, run_ai_batch=False)  # ADR-05：補抓後不跑 AI 批次

                failed = fetch_status.get_snapshot()["status"] == "error"
                _mark_throttle(market, "failed" if failed else "done")
                logger.info(f"[自動補抓] {market} 完成，status={'failed' if failed else 'done'}")
            except Exception as e:
                logger.error(f"[自動補抓] {market} 發生例外: {e}")
                _mark_throttle(market, "failed")
            finally:
                invalidate_report_cache(market)


async def catch_up(markets: Optional[list[str]] = None, force: bool = False) -> dict:
    """對外唯一入口（§3.4）。回傳 `{"markets": {market: {report, action, reason}}, "fetch": snapshot}`。"""
    requested = markets or get_enabled_markets()

    async with _get_catchup_lock():
        schedule_config = get_schedule_config()
        now_local = datetime.now(pytz.timezone(schedule_config["timezone"]))
        now_mono = time.monotonic()

        results: dict[str, dict] = {}
        stale_by_market: dict[str, dict] = {}
        triggered: list[str] = []

        for market in requested:
            report = await build_market_report(market)
            is_running = fetch_status.get_snapshot()["is_running"]
            throttle_state = get_throttle_state(market)

            action, reason = decide_action(
                report=report, is_fetch_running=is_running, now=now_local,
                schedule_config=schedule_config, throttle_state=throttle_state,
                now_mono=now_mono, force=force,
            )
            results[market] = {"report": report, "action": action, "reason": reason}

            if action == "triggered":
                _register_throttle(market, report["expected_date"])
                stale_by_market[market] = {"stocks": report["stocks"]["stale"], "indices": report["indices"]["stale"]}
                triggered.append(market)

        if triggered:
            ordered = [m for m in _WORKER_MARKET_ORDER if m in triggered] + \
                      [m for m in triggered if m not in _WORKER_MARKET_ORDER]
            thread = threading.Thread(
                target=_catch_up_worker, args=(ordered, stale_by_market), daemon=True,
                name="auto-catchup-worker",
            )
            thread.start()

    return {"markets": results, "fetch": fetch_status.get_snapshot()}
