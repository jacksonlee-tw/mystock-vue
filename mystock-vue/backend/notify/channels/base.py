"""
notify/channels/base.py
管道轉接抽象層（§4.3，ADR-14）
ChannelAdapter ABC + Capability + SendResult + FailureKind
新增管道時唯一需要新增檔案的位置（鐵則 R2、AC-19）
"""
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("mystock-backend")

# ── FailureKind ────────────────────────────────────────────────
class FailureKind(str, Enum):
    NONE               = "none"
    TRANSIENT          = "transient"           # 網路逾時、5xx → 退避重試
    RATE_LIMITED       = "rate_limited"        # 429 → 依對方指定秒數重排
    PERMANENT_ADDRESS  = "permanent_address"   # 位址無效 → dead + 停用端點
    PERMANENT_BLOCKED  = "permanent_blocked"   # 遭使用者封鎖 → dead + 停用 + SYSTEM_HEALTH
    AUTH_FAILED        = "auth_failed"         # 認證失敗 → dead + 管道 misconfigured
    QUOTA_EXCEEDED     = "quota_exceeded"      # 每日寄送預算達標 → 走備援或 dead


# ── Capability ────────────────────────────────────────────────
@dataclass
class Capability:
    rich_text:      bool = False
    subject_line:   bool = False
    link_button:    bool = False
    attachment:     bool = False
    max_body_length: int = 4096


# ── SendResult ────────────────────────────────────────────────
@dataclass
class SendResult:
    ok:                  bool        = False
    failure_kind:        FailureKind = FailureKind.NONE
    failure_reason:      str         = ""
    provider_message_id: str         = ""
    latency_ms:          int         = 0
    retry_after_sec:     int         = 0     # RATE_LIMITED 時使用


# ── HealthResult ──────────────────────────────────────────────
@dataclass
class HealthResult:
    ok:     bool = False
    detail: str  = ""


# ── ChannelAdapter ABC ────────────────────────────────────────
class ChannelAdapter(ABC):
    """
    所有管道轉接器的抽象基底類別。
    新增管道時：繼承此類 → 實作四個抽象方法 → 在 __init__.py import（ADR-14）
    """
    code:         str        # 管道代碼，對應 notify_channel.channel_code
    display_name: str        # 顯示名稱
    capabilities: Capability # 能力宣告

    @abstractmethod
    async def send(
        self,
        subject: str | None,
        body: str,
        address: str,
        settings: dict,
    ) -> SendResult:
        """發送單則訊息，回傳 SendResult（不得拋例外，失敗以 ok=False 回傳）"""
        ...

    @abstractmethod
    async def health_check(self, settings: dict, test_addresses: list[str] | None = None) -> HealthResult:
        """
        連線測試，不寫入任何資料（UC-09）。
        test_addresses：該管道目前已驗證且啟用中的收件位址（由呼叫端查好傳入，channels/ 不得直接查 DB，鐵則 R3）。
        多數管道（如 Email）光測連線/認證即可判斷是否可用，可忽略此參數；
        Incoming Webhook 類管道（Slack）沒有唯讀查詢 API，本來就得送出試發訊息才能驗證；
        Telegram 的 getMe 雖可驗證 Token，但收到「連線測試通過」不代表使用者真的會收到訊息，
        故有位址時應一併送出試發訊息，讓測試結果更貼近實際使用情境。
        """
        ...

    @abstractmethod
    def normalize_address(self, raw: str) -> str:
        """標準化收件位址（Email 小寫、Telegram chat_id str 化等）"""
        ...

    @abstractmethod
    def classify_failure(self, exc: Exception) -> FailureKind:
        """將例外分類為 FailureKind，供 dispatcher 決定重試策略"""
        ...

    def validate_settings(self, settings: dict) -> list[str]:
        """
        驗證管道設定完整性，回傳錯誤清單（空串列代表合法）。
        子類別可覆寫以加強驗證。
        """
        return []
