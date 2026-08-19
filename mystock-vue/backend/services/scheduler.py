"""APScheduler 排程（phase3_5 設計文件第 3 節）：台股／美股每日抓取＋掃描。

抓取時間不再寫死：由 config.get_schedule_config() 自 .env 讀取（預設台股 14:30、美股 06:00，
Asia/Taipei），並可透過 `PUT /api/v1/schedule` 於執行中即時套用（apply_schedule_config()），
不需重啟服務。各市場的健康檢查時間跟著抓取時間走（抓取後 HEALTH_CHECK_DELAY_MINUTES 分鐘），
否則改了抓取時間會讓健康檢查跑在抓取之前，報出假警報。

用 AsyncIOScheduler 而非 BackgroundScheduler：排程與 FastAPI 共用同一個 event loop 生命週期，
job 函式本身是同步阻塞的（requests + time.sleep），APScheduler 預設用 ThreadPoolExecutor 執行，
不會卡住主 event loop，也維持 repositories/stock_repository.py 的 run_async() 只在「非既有 loop」情境下被呼叫的前提。

整合訊息通知平台的接縫（ADR-13）也掛在這裡：_publish_after_scan() 是唯一允許同時知道
「策略掃描剛完成」與「通知平台存在」的地方；strategies/scanner.py 和 services/fetcher.py
本身完全不 import notify 任何東西（鐵則 R1）。摘要彙整／暫停到期／卡單回收／健康檢查等
背景工作是原生 async 函式，AsyncIOScheduler 會直接排進主 event loop（不經過執行緒池）。
"""
import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import get_schedule_config
from services.fetcher import fetch_status, run_fetch_process
from services.us_fetcher import run_us_fetch_process

logger = logging.getLogger("mystock-backend")

TAIPEI_TZ = "Asia/Taipei"

FETCH_JOB_IDS = {"tw": "tw_daily_fetch", "us": "us_daily_fetch"}
HEALTH_JOB_IDS = {"tw": "notify_health_tw", "us": "notify_health_us"}
HEALTH_CHECK_DELAY_MINUTES = 60

# 目前執行中的 scheduler 實例；供 API 端即時改排程用（單一 uvicorn 程序內只有一個）
_scheduler: AsyncIOScheduler | None = None


def _publish_after_scan(market: str, scan_result: dict) -> None:
    """通知平台接縫：把 scan_market_sync() 已算好的警示清單交給 notify.intake（AC-15）。
    整段 try/except 保護，通知失敗絕不讓排程主流程感知到（鐵則 R7）。"""
    try:
        from notify import config as notify_config
        if not notify_config.is_enabled():
            return
        alerts = scan_result.get("alerts") or []
        if not alerts:
            return
        trade_date = alerts[0].get("trade_date", "")

        async def _run():
            from db.session import get_async_session
            from notify.intake import publish_alert_signals
            async with get_async_session() as session:
                await publish_alert_signals(market, trade_date, alerts, session)
                await session.commit()

        asyncio.run(_run())
        logger.info(f"[通知] {market} 已發佈 {len(alerts)} 筆警示訊號事件")
    except Exception as e:
        logger.warning(f"[通知] {market} 警示事件發佈失敗（已靜默）: {e}")


def _publish_fetch_result(market: str) -> None:
    """FETCH_COMPLETED / FETCH_FAILED 事件（§4.1）：依 fetch_status 快照判斷本次抓取結果。
    fetch_status 未追蹤逐檔失敗清單，failed_symbols 暫留空陣列（見系統開發規格書 §8.2 說明）。"""
    try:
        from notify import config as notify_config
        if not notify_config.is_enabled():
            return
        snap = fetch_status.get_snapshot()
        trade_date = datetime.now().strftime("%Y-%m-%d")

        async def _run():
            from db.session import get_async_session
            from notify.intake import publish_fetch_completed, publish_fetch_failed
            async with get_async_session() as session:
                if snap.get("status") == "error":
                    await publish_fetch_failed(market, trade_date, snap.get("error") or "未知錯誤", [], session)
                else:
                    await publish_fetch_completed(market, trade_date, {
                        "success_count": snap.get("total_steps", 0),
                        "failure_count": 0,
                        "elapsed_sec": None,
                    }, session)
                await session.commit()

        asyncio.run(_run())
    except Exception as e:
        logger.warning(f"[通知] {market} 抓取結果事件發佈失敗（已靜默）: {e}")


def _scan_after_fetch(market: str) -> None:
    """盤後掃描（均線策略警示系統 設計文件 Phase 4a-7）：串接在每日抓取排程之後執行。
    比照 db/dual_write.py 的容錯慣例 —— 掃描失敗只記警告，絕不讓爬蟲流程被拖垮。"""
    try:
        from strategies.scanner import scan_market_sync
        result = scan_market_sync(market)
        logger.info(f"[排程] {market} 策略掃描完成: {result}")
        _publish_after_scan(market, result)
    except Exception as e:
        logger.warning(f"[排程] {market} 策略掃描失敗: {e}")


def _run_if_idle(market: str, fetch_fn) -> None:
    """排程與手動觸發共用同一個 fetch_status 單例；有任務進行中就跳過本次，不排隊等待（見設計文件第 3.4 節）。"""
    if fetch_status.get_snapshot()["is_running"]:
        logger.info(f"[排程] 已有抓取任務進行中，跳過本次 {market} 排程")
        return
    fetch_fn(trigger_type="scheduled")
    _publish_fetch_result(market)
    _scan_after_fetch(market)


def _scheduled_tw() -> None:
    # 1. 執行全市場每日資料作業鏈（選股功能與爬蟲 規格書 §3.3）
    try:
        from services.market_fetcher import market_fetcher
        market_fetcher.run_daily_pipeline()
    except Exception as e:
        logger.warning(f"[排程] 全市場每日抓取作業鏈異常: {e}")

    # 2. 既有追蹤清單抓取、通知與策略掃描
    _run_if_idle("tw", run_fetch_process)


def _scheduled_monthly_revenue() -> None:
    """每月 11 號 09:00 自動抓取上市月營收（選股功能與爬蟲 規格書 §3.3）。

    透過 market_fetcher 單例的 fetch_revenue_now()（而非直接 new 一個 MarketRepository()）—— 這裡是
    APScheduler 的 ThreadPoolExecutor 執行緒，直接 new 預設 MarketRepository() 會沿用主 loop 的全域
    engine，被 run_async() 內開的新事件迴圈把連線綁死，弄壞 FastAPI 主 loop（見
    market_repository.py run_async() 的說明）；market_fetcher.repo 已是背景專用連線池。"""
    try:
        from services.market_fetcher import market_fetcher
        result = market_fetcher.fetch_revenue_now(trigger_type="scheduled")
        logger.info(f"[排程] 每月營收抓取完成: {result}")
    except Exception as e:
        logger.warning(f"[排程] 每月營收抓取失敗: {e}")


def _scheduled_us() -> None:
    _run_if_idle("us", run_us_fetch_process)


# ── 整合訊息通知平台的背景工作（原生 async，AsyncIOScheduler 直接排入主 event loop）──
async def _notify_digest_tick() -> None:
    try:
        from notify import config as notify_config
        if not notify_config.is_enabled():
            return
        from db.session import get_async_session
        from notify.digest import tick
        async with get_async_session() as session:
            await tick(session)
            await session.commit()
    except Exception as e:
        logger.warning(f"[通知] 摘要彙整 tick 失敗（已靜默）: {e}")


async def _notify_pause_recovery() -> None:
    """暫停到期自動恢復（FR-SS-06，AC-23）：直接清除已過期的 pause_until。"""
    try:
        from notify import config as notify_config
        if not notify_config.is_enabled():
            return
        from db.session import get_async_session
        from sqlalchemy import text
        async with get_async_session() as session:
            await session.execute(text(
                "UPDATE notify_endpoint SET pause_until = NULL WHERE pause_until IS NOT NULL AND pause_until <= NOW()"
            ))
            await session.commit()
    except Exception as e:
        logger.warning(f"[通知] 暫停恢復檢查失敗（已靜默）: {e}")


async def _notify_stuck_recovery() -> None:
    """卡單回收（NFR-02，AC-32）"""
    try:
        from notify import config as notify_config
        if not notify_config.is_enabled():
            return
        from db.session import get_async_session
        from repositories.notify_repository import NotifyRepository
        from notify.dispatcher import recover_stuck_jobs
        async with get_async_session() as session:
            await recover_stuck_jobs(NotifyRepository(session))
            await session.commit()
    except Exception as e:
        logger.warning(f"[通知] 卡單回收失敗（已靜默）: {e}")


async def _notify_health_check(market: str) -> None:
    try:
        from notify import config as notify_config
        if not notify_config.is_enabled():
            return
        from db.session import get_async_session
        from notify.health_probe import check_market_fetch
        async with get_async_session() as session:
            await check_market_fetch(market, session)
            await session.commit()
    except Exception as e:
        logger.warning(f"[通知] {market} 健康檢查失敗（已靜默）: {e}")


async def _notify_health_check_tw() -> None:
    await _notify_health_check("tw")


async def _notify_health_check_us() -> None:
    await _notify_health_check("us")


async def _notify_purge_logs() -> None:
    try:
        from notify import config as notify_config
        if not notify_config.is_enabled():
            return
        from db.session import get_async_session
        from repositories.notify_repository import NotifyRepository
        async with get_async_session() as session:
            repo = NotifyRepository(session)
            n = await repo.purge_old_logs(notify_config.get_log_retention_days())
            await session.commit()
            if n:
                logger.info(f"[通知] 已清理 {n} 筆逾期投遞紀錄")
    except Exception as e:
        logger.warning(f"[通知] 紀錄清理失敗（已靜默）: {e}")


_FETCH_JOB_FUNCS = {"tw": _scheduled_tw, "us": _scheduled_us}
_HEALTH_JOB_FUNCS = {"tw": _notify_health_check_tw, "us": _notify_health_check_us}


def _sync_market_jobs(scheduler: AsyncIOScheduler, config: dict) -> None:
    """依設定建立／改期／移除各市場的抓取 job 與其健康檢查 job。

    停用的市場直接移除 job 而不是留著暫停的 job —— 這樣 get_schedule_status() 回報的
    「下次執行時間」才不會留下誤導性的殘值。
    """
    tz = config["timezone"]
    for market, job_id in FETCH_JOB_IDS.items():
        setting = config["markets"][market]
        health_id = HEALTH_JOB_IDS[market]

        if not setting["enabled"]:
            for jid in (job_id, health_id):
                if scheduler.get_job(jid):
                    scheduler.remove_job(jid)
            logger.info(f"[排程] {market} 每日抓取已停用")
            continue

        trigger = CronTrigger(hour=setting["hour"], minute=setting["minute"], timezone=tz)
        if scheduler.get_job(job_id):
            scheduler.reschedule_job(job_id, trigger=trigger)
        else:
            scheduler.add_job(_FETCH_JOB_FUNCS[market], trigger, id=job_id)

        # 健康檢查跟著抓取時間走，避免檢查跑在抓取之前而誤報
        total = setting["hour"] * 60 + setting["minute"] + HEALTH_CHECK_DELAY_MINUTES
        h_trigger = CronTrigger(hour=(total // 60) % 24, minute=total % 60, timezone=tz)
        if scheduler.get_job(health_id):
            scheduler.reschedule_job(health_id, trigger=h_trigger)
        else:
            scheduler.add_job(_HEALTH_JOB_FUNCS[market], h_trigger, id=health_id)

        logger.info(f"[排程] {market} 每日抓取 {setting['time']}（健康檢查 +{HEALTH_CHECK_DELAY_MINUTES} 分）({tz})")


def create_scheduler() -> AsyncIOScheduler:
    global _scheduler
    config = get_schedule_config()
    scheduler = AsyncIOScheduler(timezone=config["timezone"])

    # 每日抓取＋掃描，以及跟著它走的健康檢查（時間可由 UI 設定）
    _sync_market_jobs(scheduler, config)

    # 整合訊息通知平台背景工作（§8.2）；NOTIFY_ENABLED=false 時每個工作自己直接返回，不消耗資源
    scheduler.add_job(_notify_digest_tick, IntervalTrigger(seconds=60), id="notify_digest_tick")
    scheduler.add_job(_notify_pause_recovery, IntervalTrigger(minutes=5), id="notify_pause_recovery")
    scheduler.add_job(_notify_stuck_recovery, IntervalTrigger(minutes=5), id="notify_stuck_recovery")
    scheduler.add_job(_notify_purge_logs, CronTrigger(hour=4, minute=0, timezone=TAIPEI_TZ), id="notify_purge_logs")

    # 每月 11 號 09:00 執行全市場月營收抓取（選股功能與爬蟲 規格書 §3.3）
    scheduler.add_job(
        _scheduled_monthly_revenue,
        CronTrigger(day=11, hour=9, minute=0, timezone=TAIPEI_TZ),
        id="monthly_revenue_tw",
    )

    _scheduler = scheduler
    return scheduler


def apply_schedule_config() -> dict:
    """重新讀取設定並套用到執行中的排程，回傳套用後的狀態。
    尚未建立 scheduler（例如測試情境）時只回報設定，不視為錯誤。"""
    if _scheduler is None:
        logger.warning("[排程] 尚無執行中的 scheduler，設定已儲存但未即時套用")
    else:
        _sync_market_jobs(_scheduler, get_schedule_config())
    return get_schedule_status()


def get_schedule_status() -> dict:
    """目前排程設定 ＋ 各市場下次執行時間（供 UI 顯示）。"""
    config = get_schedule_config()
    for market, job_id in FETCH_JOB_IDS.items():
        job = _scheduler.get_job(job_id) if _scheduler else None
        next_run = getattr(job, "next_run_time", None) if job else None
        config["markets"][market]["next_run_at"] = next_run.isoformat() if next_run else None
    config["health_check_delay_minutes"] = HEALTH_CHECK_DELAY_MINUTES
    config["scheduler_running"] = bool(_scheduler and _scheduler.running)
    return config
