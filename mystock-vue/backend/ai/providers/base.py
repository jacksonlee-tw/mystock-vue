"""
ai/providers/base.py
Provider 轉接抽象層（見規格書 §4.3）。比照 notify/channels/base.py 的 ChannelAdapter 慣例：
新增 Provider 時繼承此類 → 實作 analyze() → 在 providers/__init__.py import 觸發自我註冊。
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from ai.schema import AnalysisReport


@dataclass
class AnalysisResult:
    report: AnalysisReport
    model: str
    stop_reason: Optional[str] = None
    truncated: bool = False
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None
    provider_request_id: Optional[str] = None
    response_meta: dict[str, Any] = field(default_factory=dict)


class AIProvider(ABC):
    code: str
    display_name: str

    @abstractmethod
    async def analyze(
        self,
        image_base64: str,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
    ) -> AnalysisResult:
        """呼叫底層 LLM 產生技術分析報告。

        model：使用者在產生報告前選擇的模型 ID（見 ai/config.py 的 *_SELECTABLE_MODELS，
        v3.4／ADR-AI-21）；未帶時退回該 Provider 的 .env 預設模型。呼叫端已用
        ai_config.is_valid_model() 驗證過，這裡不再重複驗證。

        必須：
        - client 於函式內延遲建立，不得在模組匯入階段要求金鑰存在（ADR-AI-05）
        - 使用非同步 SDK 客戶端（ADR-AI-04）
        - 不得讓 SDK 原生例外穿透，一律轉為 ai/errors.py 的型別（規格書 §4.7）
        """
        ...
