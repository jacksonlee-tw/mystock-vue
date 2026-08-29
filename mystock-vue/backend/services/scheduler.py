"""APScheduler 排程（phase3_5 設計文件第 3 節）：台股 14:30 / 美股 06:00（Asia/Taipei）。

用 AsyncIOScheduler 而非 BackgroundScheduler：排程與 FastAPI 共用同一個 event loop 生命週期，
job 函式本身是同步阻塞的（requests + time.sleep），APScheduler 預設用 ThreadPoolExecutor 執行，
不會卡住主 event loop，也維持 repositories/stock_repository.py 的 run_async() 只在「非既有 loop」情境下被呼叫的前提。
"""
import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import get_schedule_config
from services import exchange_rate_fetcher
from services.fetcher import fetch_status, run_fetch_process
from services.index_fetcher import run_index_fetch_process
from services.market_fetcher import market_fetcher
from services.us_fetcher import run_us_fetch_process

logger = logging.getLogger("mystock-backend")

TAIPEI_TZ = "Asia/Taipei"
JOB_IDS = {"tw": "tw_daily_fetch", "us": "us_daily_fetch"}

_scheduler: Optional[AsyncIOScheduler] = None


def _run_if_idle(market: str, fetch_fn) -> None:
    """排程與手動觸發共用同一個 fetch_status 單例；有任務進行中就跳過本次，不排隊等待（見設計文件第 3.4 節）。"""
    if fetch_status.get_snapshot()["is_running"]:
        logger.info(f"[排程] 已有抓取任務進行中，跳過本次 {market} 排程")
        return
    fetch_fn(trigger_type="scheduled")


def _fetch_indices(market: str) -> None:
    """大盤指數與台股各類股指數獨立於個股抓取進行，兩者共用 fetch_status 互斥旗標。"""
    run_index_fetch_process(market=market, trigger_type="scheduled")


def _scheduled_tw() -> None:
    _fetch_indices("tw")
    market_fetcher.run_daily_pipeline()
    exchange_rate_fetcher.fetch_exchange_rates_now(trigger_type="scheduled")
    _run_if_idle("tw", run_fetch_process)


def _scheduled_us() -> None:
    _fetch_indices("us")
    _run_if_idle("us", run_us_fetch_process)


def create_scheduler() -> AsyncIOScheduler:
    global _scheduler
    scheduler = AsyncIOScheduler(timezone=TAIPEI_TZ)
    config = get_schedule_config()
    fetch_fns = {"tw": _scheduled_tw, "us": _scheduled_us}
    for market, job_id in JOB_IDS.items():
        market_cfg = config["markets"][market]
        trigger = CronTrigger(hour=market_cfg["hour"], minute=market_cfg["minute"], timezone=config["timezone"])
        scheduler.add_job(fetch_fns[market], trigger, id=job_id, name=f"{market}_daily_fetch")
        if not market_cfg["enabled"]:
            scheduler.pause_job(job_id)
    _scheduler = scheduler
    return scheduler


def get_schedule_status() -> dict:
    """排程設定 + 執行中 APScheduler job 的下次執行時間（GET /api/v1/schedule）。"""
    config = get_schedule_config()
    markets = {}
    for market, job_id in JOB_IDS.items():
        market_cfg = dict(config["markets"][market])
        job = _scheduler.get_job(job_id) if _scheduler else None
        market_cfg["next_run_time"] = job.next_run_time.isoformat() if job and job.next_run_time else None
        markets[market] = market_cfg
    return {"timezone": config["timezone"], "markets": markets}


def apply_schedule_config() -> dict:
    """把 .env 最新排程設定套用到執行中的 scheduler（PUT /api/v1/schedule 存檔後即時生效）。"""
    if _scheduler is None:
        raise RuntimeError("排程尚未啟動")
    config = get_schedule_config()
    for market, job_id in JOB_IDS.items():
        market_cfg = config["markets"][market]
        trigger = CronTrigger(hour=market_cfg["hour"], minute=market_cfg["minute"], timezone=config["timezone"])
        _scheduler.reschedule_job(job_id, trigger=trigger)
        if market_cfg["enabled"]:
            _scheduler.resume_job(job_id)
        else:
            _scheduler.pause_job(job_id)
    return get_schedule_status()
