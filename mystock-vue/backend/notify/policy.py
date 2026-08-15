"""
notify/policy.py
M3 通知政策（§4.5）
apply_gates()：對每個 endpoint 應用四道政策閘門，回傳 GateResult
閘門 0（端點可用）+ 閘門 1（去重）+ 閘門 2（每日上限）+ 閘門 3（靜音時段）+ 閘門 4（摘要 / 緊急模式）
鐵則 R6：policy.py 不得 import channels/
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta, timezone
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo

from notify.events import Severity
from notify.timeutil import parse_time

logger = logging.getLogger("mystock-backend")


class GateDecision(str, Enum):
    SEND             = "pending"           # 放行，立即發送
    SKIP_DUPLICATE   = "skipped_duplicate" # 去重
    SKIP_PAUSED      = "skipped_paused"    # 端點暫停中
    DEFERRED         = "deferred"          # 靜音時段延後
    THROTTLED        = "throttled"         # 超過每日上限（Phase 3）
    DIGEST_PENDING   = "digest_pending"    # 摘要模式（Phase 3）
    DEAD             = "dead"              # 端點不可用


@dataclass
class GateResult:
    decision:      GateDecision = GateDecision.SEND
    reason:        str          = ""
    scheduled_at:  datetime | None = None  # 延後發送時間


async def apply_gates(
    event: Any,          # notify.events.Event
    endpoint: dict,
    idempotency_key: str,
    repo: Any,
) -> GateResult:
    """
    對單一 endpoint 應用政策閘門（由 intake.py 呼叫，§4.5）。
    閘門依序執行，第一個不放行的閘門直接回傳。
    critical severity 跳過閘門 2/3/4（見 §4.5 Critical 豁免）。
    """
    is_critical = event.severity == Severity.CRITICAL

    # ── 閘門 0：端點可用性（§4.5）────────────────────────────
    gate0 = await _gate0_endpoint_available(endpoint)
    if gate0 is not None:
        return gate0

    # ── 閘門 1：去重（§4.5，ADR-11）─────────────────────────
    gate1 = await _gate1_dedup(idempotency_key, endpoint["id"], repo)
    if gate1 is not None:
        return gate1

    # ── 閘門 2：每日上限（Phase 3，§4.5）─────────────────────
    if not is_critical:
        gate2 = await _gate2_daily_limit(endpoint, repo)
        if gate2 is not None:
            return gate2

    # ── 閘門 3：靜音時段（Phase 3，§4.5）─────────────────────
    if not is_critical:
        gate3 = _gate3_quiet_hours(endpoint)
        if gate3 is not None:
            return gate3

    # ── 閘門 4：摘要模式（Phase 3，§4.5）─────────────────────
    if not is_critical:
        gate4 = _gate4_digest_mode(endpoint)
        if gate4 is not None:
            return gate4

    return GateResult(decision=GateDecision.SEND)


# ── 閘門 0：端點可用性 ────────────────────────────────────────
async def _gate0_endpoint_available(endpoint: dict) -> GateResult | None:
    """
    閘門 0：端點狀態不可用（disabled / unsubscribed / 未驗證）→ skip
    暫停中 → skipped_paused（AC-23，不補送）
    """
    status        = endpoint.get("status", "")
    verify_status = endpoint.get("verify_status", "")
    pause_until   = endpoint.get("pause_until")

    if status in ("disabled", "unsubscribed"):
        return GateResult(GateDecision.DEAD, reason=f"端點狀態={status}")

    if verify_status != "verified":
        return GateResult(GateDecision.DEAD, reason="端點尚未驗證")

    # 暫停中：pause_until 正常情況下是 asyncpg 讀回的原生 datetime（TIMESTAMPTZ 欄位），
    # 這裡仍相容字串格式作為防禦（例如測試時傳入 dict mock），兩種輸入都要能正確判斷，
    # 不可讓字串以外的型別直接跳過整段判斷（原本的寫法只在 isinstance(..., str) 時才比較，
    # 修正前會讓真正從資料庫讀回的 datetime 物件完全略過暫停判斷，AC-23 永遠不會生效）。
    if pause_until:
        now = datetime.now(timezone.utc)
        pause_until_dt: datetime | None = None
        if isinstance(pause_until, str):
            try:
                pause_until_dt = datetime.fromisoformat(pause_until)
            except ValueError:
                pause_until_dt = None
        elif isinstance(pause_until, datetime):
            pause_until_dt = pause_until

        if pause_until_dt is not None:
            if pause_until_dt.tzinfo is None:
                pause_until_dt = pause_until_dt.replace(tzinfo=timezone.utc)
            if now < pause_until_dt:
                return GateResult(GateDecision.SKIP_PAUSED, reason=f"端點暫停至 {pause_until_dt.isoformat()}")

    return None


# ── 閘門 1：去重 ──────────────────────────────────────────────
async def _gate1_dedup(idempotency_key: str, endpoint_id: int, repo: Any) -> GateResult | None:
    """
    閘門 1：若 (idempotency_key, endpoint_id) 已存在（唯一索引衝突）→ skipped_duplicate
    Phase 1 實作：查詢而非依賴例外（dispatcher 寫入時再次保護）
    """
    exists = await repo.message_exists(idempotency_key, endpoint_id)
    if exists:
        return GateResult(GateDecision.SKIP_DUPLICATE, reason="相同冪等鍵已存在訊息單")
    return None


def _endpoint_tz(endpoint: dict) -> ZoneInfo:
    try:
        return ZoneInfo(endpoint.get("timezone") or "Asia/Taipei")
    except Exception:
        return ZoneInfo("Asia/Taipei")


_as_time = parse_time  # endpoint.quiet_start/quiet_end 依驅動可能回傳 datetime.time 或 'HH:MM[:SS]' 字串；共用邏輯見 notify/timeutil.py


# ── 閘門 2：每日上限（FR-PL-02、FR-PL-09：依端點時區計算日期邊界）─
async def _gate2_daily_limit(endpoint: dict, repo: Any) -> GateResult | None:
    """
    閘門 2：今日（依端點時區）已發送則數達 daily_limit → throttled，併入摘要（不遺失，FR-PL-02）。
    未達上限則遞增計數並放行。
    """
    daily_limit = endpoint.get("daily_limit") or 30
    local_date: date = datetime.now(_endpoint_tz(endpoint)).date()
    used = await repo.get_quota_usage("endpoint", endpoint.get("endpoint_code", str(endpoint["id"])), local_date)
    if used >= daily_limit:
        return GateResult(GateDecision.THROTTLED, reason=f"今日已達每日上限 {daily_limit} 則")
    await repo.increment_quota("endpoint", endpoint.get("endpoint_code", str(endpoint["id"])), local_date)
    return None


# ── 閘門 3：靜音時段（FR-PL-03、FR-PL-09：僅延後，不改摘要）───────
def _gate3_quiet_hours(endpoint: dict) -> GateResult | None:
    """
    閘門 3：現在在端點的靜音時段內 → deferred，scheduled_at 設為靜音結束時刻（當地時區換算回 UTC）。
    支援跨午夜區間（start > end，例如 22:00–08:00）。未設定靜音時段則不過濾。
    """
    start = _as_time(endpoint.get("quiet_start"))
    end   = _as_time(endpoint.get("quiet_end"))
    if start is None or end is None or start == end:
        return None

    tz  = _endpoint_tz(endpoint)
    now_local = datetime.now(tz)
    t   = now_local.time()

    if start > end:
        in_quiet = t >= start or t < end
    else:
        in_quiet = start <= t < end
    if not in_quiet:
        return None

    # 計算靜音結束的下一個當地時間點（可能是今天或明天）
    end_today = now_local.replace(hour=end.hour, minute=end.minute, second=end.second, microsecond=0)
    end_at = end_today if end_today > now_local else end_today + timedelta(days=1)
    if start > end and t >= start:
        # 現在在「今晚」的靜音起點之後 → 結束時刻落在明天
        end_at = end_today + timedelta(days=1)

    scheduled_at_utc = end_at.astimezone(timezone.utc)
    return GateResult(GateDecision.DEFERRED, reason="目前在靜音時段", scheduled_at=scheduled_at_utc)


# ── 閘門 4：摘要 / 緊急模式（FR-PL-05）──────────────────────────
def _gate4_digest_mode(endpoint: dict) -> GateResult | None:
    """
    閘門 4：
    - delivery_mode=digest → 一律併入摘要（digest_pending）
    - delivery_mode=critical_only → 非 critical 事件（能走到這裡代表已非 critical）併入摘要
    - delivery_mode=realtime → 放行（None）
    """
    mode = endpoint.get("delivery_mode", "realtime")
    if mode in ("digest", "critical_only"):
        return GateResult(GateDecision.DIGEST_PENDING, reason=f"端點模式={mode}，併入下一次摘要")
    return None
