"""
notify/channel_config.py
M11 管道設定：Fernet 加解密憑證（ADR-08）、連線測試、熔斷狀態機（§4.8）
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timedelta, timezone

from notify import config as notify_config
from notify.security import mask_settings

logger = logging.getLogger("mystock-backend")


# ── Fernet 加解密（ADR-08）────────────────────────────────────
def _get_fernet():
    from cryptography.fernet import Fernet
    key = notify_config.get_secret_key()
    if not key:
        raise RuntimeError("NOTIFY_SECRET_KEY 未設定，無法加解密管道憑證")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_settings(settings: dict) -> str:
    """把 settings dict 序列化後加密，回傳 Fernet 密文（字串）"""
    f = _get_fernet()
    raw = json.dumps(settings, ensure_ascii=False).encode()
    return f.encrypt(raw).decode()


def decrypt_settings(ciphertext: str) -> dict:
    """解密 Fernet 密文，回傳 settings dict"""
    if not ciphertext:
        return {}
    if not notify_config.get_secret_key():
        logger.error("[通知] NOTIFY_SECRET_KEY 未設定，無法解密管道設定")
        return {}
    try:
        f   = _get_fernet()
        raw = f.decrypt(ciphertext.encode())
        return json.loads(raw)
    except Exception as exc:
        logger.error("[通知] 解密管道設定失敗（%s）：%s", type(exc).__name__, exc)
        return {}


# ── 連線測試（UC-09）──────────────────────────────────────────
async def test_connection(channel_code: str, settings: dict) -> dict:
    """
    呼叫對應管道的 health_check()，不修改任何資料。
    回傳 {"ok": bool, "detail": str, "latency_ms": int}
    """
    import time
    from notify.channels import get_channel

    adapter = get_channel(channel_code)
    if adapter is None:
        return {"ok": False, "detail": f"未知管道代碼：{channel_code}", "latency_ms": 0}

    start  = time.monotonic()
    result = await adapter.health_check(settings)
    ms     = int((time.monotonic() - start) * 1000)
    return {"ok": result.ok, "detail": result.detail, "latency_ms": ms}


# ── 熔斷狀態機（§4.8，ADR-15）────────────────────────────────
def compute_circuit_backoff(consecutive_failures: int) -> int:
    """
    指數退避，上限為 NOTIFY_CIRCUIT_COOLDOWN_MAX_SEC。
    consecutive_failures=0 回傳 0（不啟動熔斷）。
    """
    threshold   = notify_config.get_circuit_threshold()
    base_sec    = notify_config.get_circuit_cooldown_sec()
    max_sec     = notify_config.get_circuit_cooldown_max_sec()
    if consecutive_failures < threshold:
        return 0
    excess  = consecutive_failures - threshold
    backoff = base_sec * (2 ** excess)
    return min(backoff, max_sec)


def should_circuit_break(channel_row: dict) -> bool:
    """
    判斷管道是否應進入熔斷（circuit_open）狀態。
    channel_row 欄位：consecutive_failures, circuit_open_until
    """
    circuit_open_until = channel_row.get("circuit_open_until")
    if circuit_open_until:
        now = datetime.now(timezone.utc)
        if isinstance(circuit_open_until, str):
            circuit_open_until = datetime.fromisoformat(circuit_open_until)
        if circuit_open_until.tzinfo is None:
            circuit_open_until = circuit_open_until.replace(tzinfo=timezone.utc)
        if now < circuit_open_until:
            return True  # 仍在熔斷冷卻期
    return False


def open_circuit_until(consecutive_failures: int) -> datetime | None:
    """計算熔斷冷卻截止時間（None 代表不需熔斷）"""
    backoff = compute_circuit_backoff(consecutive_failures)
    if backoff == 0:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=backoff)


# ── 管道設定驗證 ──────────────────────────────────────────────
def validate_channel_settings(channel_code: str, settings: dict) -> list[str]:
    """驗證管道設定完整性，回傳錯誤清單"""
    from notify.channels import get_channel
    adapter = get_channel(channel_code)
    if adapter is None:
        return [f"未知管道代碼：{channel_code}"]
    return adapter.validate_settings(settings)
