"""
notify/security.py
安全工具（§7.1、§7.2、§7.3）
- authenticate_self_service_token：自助端 Cookie 授權
- mask_settings：遮蔽機敏欄位（NFR-08）
- redact：過濾 logger 輸出中的機敏字串
- RateLimiter：記憶體速率限制（自助端、token 嘗試）
"""
from __future__ import annotations
import hashlib
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import Request
from itsdangerous import TimestampSigner, SignatureExpired, BadSignature

from notify import config as notify_config

logger = logging.getLogger("mystock-backend")

# ── 機敏欄位清單（ADR-08，NFR-08）──────────────────────────────
SECRET_FIELDS = frozenset({
    "smtp_password", "bot_token", "api_key", "access_token",
    "secret", "password", "token", "credential",
})
SECRET_PATTERNS = [
    "smtp_password=", "bot_token=", "password=",
]
MASKED_VALUE = "••••••••"


# ── 遮蔽與清理 ───────────────────────────────────────────────
def mask_settings(settings: dict) -> dict:
    """把 settings dict 中的機敏欄位替換為 MASKED_VALUE（API 回應用）"""
    result = {}
    for k, v in settings.items():
        if any(sec in k.lower() for sec in SECRET_FIELDS):
            result[k] = MASKED_VALUE
            result["_masked"] = True
        else:
            result[k] = v
    return result


def redact(text: str) -> str:
    """過濾 log 字串中可能含有機敏值的片段（§7.1 日誌保護）"""
    for pattern in SECRET_PATTERNS:
        if pattern in text:
            idx = text.index(pattern) + len(pattern)
            end = text.find(" ", idx)
            if end == -1:
                end = min(idx + 50, len(text))
            text = text[:idx] + MASKED_VALUE + text[end:]
    return text[:300]


def sha256_hex(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class NotifyUnauthorizedException(Exception):
    pass


class NotifyForbiddenException(Exception):
    pass


class NotifyNotFoundException(Exception):
    pass


class NotifyValidationException(Exception):
    pass


class ChannelUnavailableException(Exception):
    pass


class PreferenceWideningException(Exception):
    pass


# ── 自助連結 Session（§7.2，ADR-09）──────────────────────────
def _self_signer() -> TimestampSigner:
    return TimestampSigner(notify_config.get_self_service_session_secret(), salt="self-session")


def create_self_service_session(recipient_id: int) -> str:
    """產生自助端 Cookie 值（帶 recipient_id 的簽章值）"""
    signer = _self_signer()
    return signer.sign(str(recipient_id)).decode()


def verify_self_service_session(cookie_value: str) -> int | None:
    """驗證自助端 Cookie，成功回傳 recipient_id，失敗回傳 None（Cookie 30 分鐘有效）"""
    signer = _self_signer()
    try:
        data = signer.unsign(cookie_value, max_age=1800)
        return int(data.decode())
    except (SignatureExpired, BadSignature, ValueError):
        return None


async def require_self_service(request: Request) -> int:
    """FastAPI dependency：驗證自助端 Cookie，回傳 recipient_id"""
    cookie = request.cookies.get("ns_session", "")
    rid = verify_self_service_session(cookie) if cookie else None
    if rid is None:
        raise NotifyUnauthorizedException("自助連結無效或已過期")
    return rid


# ── 速率限制（記憶體，§7.2）──────────────────────────────────
class RateLimiter:
    """簡單的記憶體速率計數器，以 (key, window_minute) 為鍵"""
    def __init__(self, max_per_minute: int = 10):
        self._max = max_per_minute
        self._counts: dict[tuple, list[float]] = defaultdict(list)

    def check(self, key: str) -> bool:
        """
        回傳 True 代表允許；False 代表超過限制。
        訊息不得透露收件人是否存在（NFR-19）。
        """
        now    = time.time()
        window = int(now // 60)
        bucket = (key, window)
        hits   = self._counts[bucket]
        # 清理舊 bucket
        self._counts = {k: v for k, v in self._counts.items() if k[1] >= window - 1}
        if len(hits) >= self._max:
            return False
        hits.append(now)
        return True


# 全域速率限制器（token 嘗試）
token_rate_limiter = RateLimiter(max_per_minute=10)
