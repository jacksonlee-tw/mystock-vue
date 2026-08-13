"""APScheduler 排程（phase3_5 設計文件第 3 節）：台股 14:30 / 美股 06:00（Asia/Taipei）。

用 AsyncIOScheduler 而非 BackgroundScheduler：排程與 FastAPI 共用同一個 event loop 生命週期，
job 函式本身是同步阻塞的（requests + time.sleep），APScheduler 預設用 ThreadPoolExecutor 執行，
不會卡住主 event loop，也維持 repositories/stock_repository.py 的 run_async() 只在「非既有 loop」情境下被呼叫的前提。
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from services.fetcher import fetch_status, run_fetch_process
from services.us_fetcher import run_us_fetch_process

logger = logging.getLogger("mystock-backend")

TAIPEI_TZ = "Asia/Taipei"


def _scan_after_fetch(market: str) -> None:
    """盤後掃描（均線策略警示系統 設計文件 Phase 4a-7）：串接在每日抓取排程之後執行。
    比照 db/dual_write.py 的容錯慣例 —— 掃描失敗只記警告，絕不讓爬蟲流程被拖垮。"""
    try:
        from strategies.scanner import scan_market_sync
        result = scan_market_sync(market)
        logger.info(f"[排程] {market} 策略掃描完成: {result}")
    except Exception as e:
        logger.warning(f"[排程] {market} 策略掃描失敗: {e}")


def _run_if_idle(market: str, fetch_fn) -> None:
    """排程與手動觸發共用同一個 fetch_status 單例；有任務進行中就跳過本次，不排隊等待（見設計文件第 3.4 節）。"""
    if fetch_status.get_snapshot()["is_running"]:
        logger.info(f"[排程] 已有抓取任務進行中，跳過本次 {market} 排程")
        return
    fetch_fn(trigger_type="scheduled")
    _scan_after_fetch(market)


def _scheduled_tw() -> None:
    _run_if_idle("tw", run_fetch_process)


def _scheduled_us() -> None:
    _run_if_idle("us", run_us_fetch_process)


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TAIPEI_TZ)
    scheduler.add_job(_scheduled_tw, CronTrigger(hour=14, minute=30, timezone=TAIPEI_TZ), id="tw_daily_fetch")
    scheduler.add_job(_scheduled_us, CronTrigger(hour=6, minute=0, timezone=TAIPEI_TZ), id="us_daily_fetch")
    return scheduler
