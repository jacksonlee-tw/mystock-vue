"""
notify/dispatcher.py
M5 Outbox Dispatcher Worker（§4.7，ADR-13）
DispatcherWorker 為常駐 asyncio.Task，在 FastAPI lifespan 啟動。
- claim_batch()：使用 FOR UPDATE SKIP LOCKED 原子取件（AC-32）
- 退避重試（NOTIFY_MAX_RETRY × NOTIFY_RETRY_BACKOFF_SEC）
- 卡單回收（stuck jobs，claimed_at 逾時）
"""
from __future__ import annotations
import asyncio
import logging
import socket
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from notify import config as notify_config
from notify.channels import get_channel
from notify.channels.base import FailureKind

logger = logging.getLogger("mystock-backend")

WORKER_ID = f"{socket.gethostname()}-{str(uuid.uuid4())[:8]}"


class DispatcherWorker:
    """
    Outbox Dispatcher：常駐 asyncio.Task，每 NOTIFY_POLL_INTERVAL_SEC 輪詢一次。
    每批最多取 NOTIFY_BATCH_SIZE 則訊息並逐一發送。
    """

    def __init__(self):
        self._running = False
        self._task:   asyncio.Task | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task    = asyncio.create_task(self._loop(), name="notify-dispatcher")
        logger.info("[通知] Dispatcher 啟動，worker_id=%s", WORKER_ID)

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[通知] Dispatcher 已停止")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._tick()
            except Exception as exc:
                logger.error("[通知] Dispatcher tick 例外：%s", exc)
            await asyncio.sleep(notify_config.get_poll_interval_sec())

    async def _tick(self) -> None:
        from db.session import get_async_session
        from repositories.notify_repository import NotifyRepository

        async with get_async_session() as session:
            repo  = NotifyRepository(session)
            batch = await repo.claim_batch(
                worker_id=WORKER_ID,
                batch_size=notify_config.get_batch_size(),
            )
            if not batch:
                return

            logger.debug("[通知] Dispatcher 取件 %d 則", len(batch))
            for msg in batch:
                await self._dispatch_one(msg, repo)
            await session.commit()

    async def _dispatch_one(self, msg: dict, repo: Any) -> None:
        channel_code = msg.get("channel_code", "")
        adapter      = get_channel(channel_code)
        msg_id       = msg.get("id")
        endpoint_id  = msg.get("endpoint_id")

        # 取得管道設定（解密）
        try:
            from notify.channel_config import decrypt_settings, should_circuit_break
            channel_row = await repo.get_channel(channel_code)
            if not channel_row:
                await repo.mark_dead(msg_id, "管道不存在")
                return

            # 熔斷檢查
            if should_circuit_break(channel_row):
                await repo.requeue_message(msg_id)
                logger.debug("[通知] 管道 %s 熔斷中，訊息 %s 重排", channel_code, msg_id)
                return

            settings = decrypt_settings(channel_row.get("settings_enc") or "")
        except Exception as exc:
            logger.warning("[通知] 取得管道設定失敗 (%s): %s", channel_code, exc)
            await repo.mark_dead(msg_id, str(exc)[:100])
            return

        if adapter is None:
            logger.warning("[通知] 未知管道代碼：%s", channel_code)
            await repo.mark_dead(msg_id, "未知管道")
            return

        # 取得收件位址
        ep = await repo.get_endpoint(endpoint_id)
        if not ep:
            await repo.mark_dead(msg_id, "端點不存在")
            return

        address = ep.get("address", "")
        subject = msg.get("subject")
        body    = msg.get("body", "")

        start = time.monotonic()
        result = await adapter.send(subject=subject, body=body, address=address, settings=settings)
        ms     = int((time.monotonic() - start) * 1000)

        if result.ok:
            await repo.mark_sent(msg_id, result.provider_message_id)
            await repo.log_attempt(msg_id, {
                "attempt_no":         msg.get("attempt_count", 0) + 1,
                "result":             "success",
                "provider_message_id": result.provider_message_id,
                "latency_ms":         ms,
            })
            from repositories.activity_log_repository import ActivityLogRepository
            await ActivityLogRepository(repo.session).log(
                "NOTIFY_MESSAGE_SENT",
                view_id="notify_dispatcher",
                detail=f"{channel_code} 通知發送成功：message_id={msg_id}, endpoint_id={endpoint_id}",
                success=True,
                rel_id=msg_id,
                comments=(f"provider_message_id={result.provider_message_id}; latency_ms={ms}")[:1024],
                created_by="system",
            )
            await repo.reset_channel_failures(channel_code)
        else:
            await self._handle_failure(msg, result, repo)

    async def _handle_failure(self, msg: dict, result: Any, repo: Any) -> None:
        from notify.channel_config import open_circuit_until

        msg_id       = msg.get("id")
        channel_code = msg.get("channel_code", "")
        attempt      = msg.get("attempt_count", 0) + 1
        max_retry    = notify_config.get_max_retry()
        backoffs     = notify_config.get_retry_backoff_sec()

        await repo.log_attempt(msg_id, {
            "attempt_no":    attempt,
            "result":        "retryable_failure" if result.failure_kind not in (
                FailureKind.PERMANENT_ADDRESS, FailureKind.PERMANENT_BLOCKED, FailureKind.AUTH_FAILED
            ) else "permanent_failure",
            "failure_kind":  result.failure_kind.value,
            "failure_reason": result.failure_reason[:300],
            "latency_ms":    result.latency_ms,
        })

        # 永久性失敗 → dead，不重試
        if result.failure_kind in (FailureKind.PERMANENT_ADDRESS, FailureKind.PERMANENT_BLOCKED, FailureKind.AUTH_FAILED):
            await repo.mark_dead(msg_id, result.failure_reason, result.failure_kind.value)
            if result.failure_kind == FailureKind.AUTH_FAILED:
                await repo.set_channel_misconfigured(channel_code)
            await self._notify_dead_health(msg, channel_code, result.failure_kind.value, repo)
            return

        # 超過重試上限 → dead
        if attempt >= max_retry:
            await repo.mark_dead(msg_id, f"超過最大重試次數 {max_retry}", result.failure_kind.value)
            await repo.increment_channel_failures(channel_code)
            await self._notify_dead_health(msg, channel_code, result.failure_kind.value, repo)
            return

        # 計算退避時間
        backoff_idx = min(attempt - 1, len(backoffs) - 1)
        backoff_sec = result.retry_after_sec or backoffs[backoff_idx]
        retry_at    = datetime.now(timezone.utc) + timedelta(seconds=backoff_sec)

        await repo.mark_failed_retry(msg_id, attempt, retry_at, result.failure_kind.value)
        await repo.increment_channel_failures(channel_code)
        logger.info(
            "[通知] 訊息 %s 失敗 attempt=%d，%d 秒後重試 (%s)",
            msg_id, attempt, backoff_sec, result.failure_kind.value
        )

    async def _notify_dead_health(self, msg: dict, channel_code: str, failure_kind: str, repo: Any) -> None:
        """訊息最終失敗（dead）時觸發具冷卻鍵的系統異常事件（FR-DP-04、AC-28）。
        本身失敗一律靜默，不得讓通知平台的告警機制反過來拖垮 dispatcher。"""
        try:
            from notify.health_probe import report_delivery_dead
            event = await repo.get_event(msg.get("event_id"))
            original_event_type = event.get("event_type", "") if event else ""
            await report_delivery_dead(original_event_type, channel_code, failure_kind, repo)
        except Exception as exc:
            logger.warning("[通知] 系統異常告警產生失敗（已靜默）：%s", exc)


async def recover_stuck_jobs(repo: Any) -> int:
    """
    卡單回收（§4.7）：claimed_at 超過 NOTIFY_STUCK_TIMEOUT_MIN 分鐘的 sending 狀態訊息
    重置為 pending，供下次 claim_batch() 重新取件（AC-32）
    """
    timeout_min = notify_config.get_stuck_timeout_min()
    cutoff      = datetime.now(timezone.utc) - timedelta(minutes=timeout_min)
    count       = await repo.recover_stuck_messages(cutoff)
    if count:
        logger.warning("[通知] 卡單回收：%d 則訊息重置為 pending", count)
    return count


# 全域 worker 實例（由 main.py lifespan 管理）
_worker: DispatcherWorker | None = None


def get_worker() -> DispatcherWorker:
    global _worker
    if _worker is None:
        _worker = DispatcherWorker()
    return _worker


async def start_dispatcher() -> None:
    if not notify_config.is_enabled():
        logger.info("[通知] NOTIFY_ENABLED=false，Dispatcher 不啟動")
        return
    get_worker().start()


async def stop_dispatcher() -> None:
    w = get_worker()
    await w.stop()
