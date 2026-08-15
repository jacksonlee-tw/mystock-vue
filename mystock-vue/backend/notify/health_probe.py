"""
notify/health_probe.py
SYSTEM_HEALTH 事件產生器（§4.1 事件類型表、§4.10 防遞迴、§8.2 排程）

兩個獨立來源都會產生 SYSTEM_HEALTH 事件：
1. check_market_fetch()：排程 15:30(TW)/07:00(US) 檢查當日抓取是否確實執行過（§8.2）
2. report_delivery_dead()：由 dispatcher 在訊息最終失敗時呼叫，通知「某管道持續送不出去」（FR-DP-04、AC-28）

**誠實聲明（Q-13、DEV-04 已確認）**：本探測器與被監控的排程同一個進程執行，
無法偵測「排程整個沒有被觸發」或「服務本身已經停止」——那需要獨立於本服務之外的
心跳檢查者，首版未提供。這裡只能在服務仍在正常運作的前提下，發現「資料/管道異常」。
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from notify import config as notify_config
from notify.events import Event, EventType, Severity

logger = logging.getLogger("mystock-backend")

# FETCH_FAILED 之外，本探測器另外追蹤的「抓取似乎沒跑」門檻
_STALE_FETCH_HOURS = 3


async def check_market_fetch(market: str, db_session: Any) -> None:
    """
    §8.2 健康檢查排程：確認今日該市場的抓取程序確實執行過。
    只能在本服務進程仍存活時才會被觸發（見檔案頂端誠實聲明）。
    """
    if not notify_config.is_enabled():
        return
    try:
        from services.fetcher import fetch_status
        snap = fetch_status.get_snapshot()

        # 案例 1：仍卡在 running 超過門檻 → 疑似卡住
        if snap.get("is_running") and snap.get("started_at"):
            started = datetime.strptime(snap["started_at"], "%Y-%m-%d %H:%M:%S")
            if datetime.now() - started > timedelta(hours=_STALE_FETCH_HOURS):
                await _publish_health(
                    probe_key=f"{market}_fetch_stuck",
                    description=f"{market.upper()} 抓取程序已執行超過 {_STALE_FETCH_HOURS} 小時仍未結束，疑似卡住",
                    db_session=db_session,
                )
            return

        # 案例 2：今日完全沒有執行紀錄（finished_at 為空或非今日）
        finished_at = snap.get("finished_at")
        today = datetime.now().strftime("%Y-%m-%d")
        if not finished_at or not finished_at.startswith(today):
            await _publish_health(
                probe_key=f"{market}_fetch_missing",
                description=f"{market.upper()} 今日尚未偵測到已完成的抓取紀錄，請確認排程是否正常觸發",
                db_session=db_session,
            )
            return

        # 案例 3：最近一次執行結果是 error
        if snap.get("status") == "error":
            await _publish_health(
                probe_key=f"{market}_fetch_error",
                description=f"{market.upper()} 最近一次抓取結果為失敗：{snap.get('error', '未知錯誤')}",
                db_session=db_session,
            )
    except Exception as exc:
        # 鐵則 R7：健康檢查本身的錯誤絕不能拖垮排程
        logger.warning("[通知] 健康檢查失敗（已靜默）：%s", exc)


async def _publish_health(probe_key: str, description: str, db_session: Any) -> None:
    from notify import intake
    cooldown_bucket = datetime.now().strftime("%Y-%m-%d")  # 同一天同一探測項目只發一次
    ev = Event(
        event_type=EventType.SYSTEM_HEALTH,
        severity=Severity.CRITICAL,
        source="health_probe",
        occurred_at=datetime.now(timezone.utc),
        payload={
            "probe_key": probe_key,
            "description": description,
            "cooldown_bucket": cooldown_bucket,
        },
        source_event_key=f"health:{probe_key}:{cooldown_bucket}",
    )
    await intake.publish(ev, db_session)


# ── 投遞失敗告警（FR-DP-04、AC-28，由 dispatcher 呼叫）──────────
async def report_delivery_dead(
    original_event_type: str,
    channel_code:        str,
    failure_kind:        str,
    repo:                Any,
) -> None:
    """
    某則訊息最終失敗（dead）時呼叫。
    - SYSTEM_HEALTH 本身的投遞失敗不得再衍生 SYSTEM_HEALTH（防止無限遞迴，FR-DP-04）
    - 同管道同失敗類型在冷卻期間只產生一則告警，其餘只累計次數（RK-11）
    """
    if original_event_type == EventType.SYSTEM_HEALTH:
        logger.debug("[通知] SYSTEM_HEALTH 投遞失敗不再衍生新事件（防遞迴）")
        return

    cooldown_key = f"delivery_dead:{channel_code}:{failure_kind}"
    cooldown_sec = notify_config.get_circuit_cooldown_sec()
    should_alert = await repo.check_and_bump_suppression(cooldown_key, cooldown_sec)
    if not should_alert:
        return  # 冷卻期內，僅由 check_and_bump_suppression 累計次數，不重複發送

    cooldown_bucket = datetime.now().strftime("%Y-%m-%d-%H")
    ev = Event(
        event_type=EventType.SYSTEM_HEALTH,
        severity=Severity.CRITICAL,
        source="dispatcher",
        occurred_at=datetime.now(timezone.utc),
        payload={
            "probe_key": f"delivery_{channel_code}_{failure_kind}",
            "description": f"管道 {channel_code} 持續發送失敗（{failure_kind}），已有訊息轉為最終失敗",
            "cooldown_bucket": cooldown_bucket,
        },
        source_event_key=f"health:delivery_{channel_code}_{failure_kind}:{cooldown_bucket}",
    )
    from notify import intake
    await intake.publish(ev, repo.session)  # 沿用同一個 session/交易
