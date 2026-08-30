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


@dataclass
class ExtractionResult:
    """`extract_structured()` 的回傳結構（見 docs/16.AI技術分析/
    Phase3-產業鏈知識圖譜與輪動模型.md ADR-IC-12）。比照 AnalysisResult，但沒有圖片相關欄位
    （沒有 K 線圖可送，也就沒有 support/resistance 這種診股報告專屬的內容）。"""
    data: Any  # 呼叫端傳入的 response_schema 型別的實例
    model: str
    stop_reason: Optional[str] = None
    truncated: bool = False
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    provider_request_id: Optional[str] = None
    response_meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchResult:
    """`research_grounded()` 的回傳結構（見 docs/16.AI技術分析/
    Phase3-產業鏈知識圖譜與輪動模型.md §4.7.7、ADR-IC-17）。跟 ExtractionResult 的差異：
    這裡沒有結構化 `data`，只有自由文字 `text` 與檢索工具帶回的真實引用來源 `citations`——
    Stage A「研究」刻意不要求結構化輸出（見 research_grounded() 的說明）。"""
    text: str
    citations: list[dict[str, str]] = field(default_factory=list)  # [{"url": ..., "title": ...}]
    model: str = ""
    query_count: Optional[int] = None
    stop_reason: Optional[str] = None
    truncated: bool = False
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
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

    async def extract_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type,
        model: str | None = None,
    ) -> ExtractionResult:
        """純文字結構化知識萃取（見 docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md
        ADR-IC-12）：industry_chain/ 模組新增的能力，供 LLM 產業鏈知識萃取使用，不含圖片。

        **非抽象方法**，預設拋 NotImplementedError——刻意不改動既有 analyze() 的抽象方法簽章，
        也不強制既有／未來的每個 Provider 都要實作這個新能力，避免對既有 analyze() 呼叫路徑
        產生任何回歸風險（AC-IC-17）。Gemini／Claude 兩個既有 Provider 皆已各自實作（見
        gemini_provider.py／claude_provider.py），本方法只在還沒接上這個能力的 Provider 上
        會被觸發。

        response_schema：呼叫端傳入的 Pydantic model 型別（如 industry_chain/schema.py 的
        ChainExtractionResult），對應既有 analyze() 寫死 LLMAnalysisReport 的做法在這裡改為
        參數化，讓本方法可服務任何結構化萃取需求，不綁死單一用途。
        """
        raise NotImplementedError(f"{self.code} Provider 尚未實作 extract_structured()")

    async def research_grounded(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        timeout_sec: int | None = None,
    ) -> ResearchResult:
        """開檢索工具做「研究」，**不**要求結構化輸出（見 docs/16.AI技術分析/
        Phase3-產業鏈知識圖譜與輪動模型.md §4.7.7、ADR-IC-17 的兩段式 grounded 萃取 Stage A）。

        **非抽象方法**，預設拋 NotImplementedError，理由同 extract_structured()：不改動既有
        analyze() 簽章、不強制每個 Provider 都要實作。

        刻意跟 extract_structured() 分成兩個獨立方法、不合併成一次「同時開工具又要結構化輸出」
        的呼叫：這兩者在多個 Gemini 版本上相容性有風險（ADR-IC-17），兩段式設計天然避開。

        timeout_sec：grounded 呼叫明顯比一般呼叫慢，呼叫端（industry_chain/research.py）會傳入
        比 AI_REQUEST_TIMEOUT_SEC 更長的逾時值；未帶時退回該 Provider 一般呼叫的預設逾時。
        """
        raise NotImplementedError(f"{self.code} Provider 尚未實作 research_grounded()")
