"""
ai/providers/gemini_provider.py
Gemini（Google）Provider 實作（見規格書 §4.3、§2 註記）。

採用現行統一 SDK `google-genai`（`from google import genai`），而非設計文件 v1.0 誤用的
舊版 `google.generativeai`（見規格書 §0.1 D-02）。

⚠️ 與 Claude 端不同：本檔的 SDK 呼叫細節（例外階層、finish_reason 列舉值、usage_metadata
欄位名稱）未經與 Anthropic SDK 同等程度的官方文件覆核，請於串接真實 GEMINI_API_KEY 測試時
複核 https://ai.google.dev/gemini-api/docs 並視情況調整（規格書 §2 已明確註記此限制）。
"""
from __future__ import annotations
import logging
import time

from ai import config as ai_config
from ai.errors import (
    AIProviderMisconfiguredException, AIRateLimitedException,
    AITimeoutException, AIProviderUnreachableException, AIProviderError,
)
from ai.providers.base import AIProvider, AnalysisResult, ExtractionResult, ResearchResult
from ai.providers import ai_provider
from ai.schema import AnalysisReport, LLMAnalysisReport, from_llm_report

logger = logging.getLogger("mystock-backend")

# finish_reason（Gemini）→ stop_reason（比照 Claude 命名，供前端／資料表共用同一份契約）
_FINISH_REASON_MAP = {
    "STOP": "end_turn",
    "MAX_TOKENS": "max_tokens",
    "SAFETY": "refusal",
    "RECITATION": "refusal",
}


@ai_provider(code="gemini", display_name="Gemini (Google)")
class GeminiProvider(AIProvider):
    async def analyze(
        self, image_base64: str, system_prompt: str, user_prompt: str, model: str | None = None,
    ) -> AnalysisResult:
        api_key = ai_config.get_gemini_api_key()
        if not api_key:
            raise AIProviderMisconfiguredException("GEMINI_API_KEY 未設定")

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise AIProviderMisconfiguredException("google-genai 套件未安裝") from exc

        model = model or ai_config.get_gemini_model()
        max_tokens = ai_config.get_max_output_tokens()
        timeout_sec = ai_config.get_request_timeout_sec()
        image_bytes = _b64_to_bytes(image_base64)

        client = genai.Client(api_key=api_key)
        started = time.monotonic()
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                    user_prompt,
                ],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=max_tokens,
                    response_mime_type="application/json",
                    response_schema=LLMAnalysisReport,
                    http_options=types.HttpOptions(timeout=timeout_sec * 1000),  # ms
                ),
            )
        except Exception as exc:  # noqa: BLE001 — 見檔頭註記：Gemini 例外階層待實測覆核
            raise _classify_gemini_error(exc) from exc
        finally:
            elapsed_ms = int((time.monotonic() - started) * 1000)

        candidate = response.candidates[0] if getattr(response, "candidates", None) else None
        raw_finish_reason = getattr(candidate, "finish_reason", None)
        # google-genai 回傳的是 FinishReason enum，str() 會印出 "FinishReason.STOP" 這種完整
        # repr、對不上下面的對照表；取 .name（enum 成員名稱，如 "STOP"）才是我們要的原始值。
        finish_reason = getattr(raw_finish_reason, "name", None) or (str(raw_finish_reason) if raw_finish_reason else "")
        stop_reason = _FINISH_REASON_MAP.get(finish_reason, finish_reason.lower() or None)
        truncated = stop_reason == "max_tokens"

        llm_report: LLMAnalysisReport | None = getattr(response, "parsed", None)
        if llm_report is not None:
            parsed = from_llm_report(llm_report)
        else:
            parsed = AnalysisReport(
                verdict="neutral",
                headline="AI 未能產生結構化結論" if stop_reason != "refusal" else "AI 婉拒本次分析請求",
                report_markdown=getattr(response, "text", None) or "（無內容）",
                confidence="low",
            )

        usage = getattr(response, "usage_metadata", None)
        return AnalysisResult(
            report=parsed,
            model=model,
            stop_reason=stop_reason,
            truncated=truncated,
            input_tokens=getattr(usage, "prompt_token_count", None) if usage else None,
            output_tokens=getattr(usage, "candidates_token_count", None) if usage else None,
            cache_read_tokens=getattr(usage, "cached_content_token_count", None) if usage else None,
            provider_request_id=None,
            response_meta={"elapsed_ms": elapsed_ms, "finish_reason": finish_reason},
        )


    async def extract_structured(
        self, system_prompt: str, user_prompt: str, response_schema: type, model: str | None = None,
    ) -> ExtractionResult:
        """純文字結構化萃取（見 ADR-IC-12）：與 analyze() 幾乎同一套呼叫骨架，差異只有
        ① 沒有圖片 part、② response_schema 是呼叫端傳入的參數而非寫死 LLMAnalysisReport。
        錯誤分類、逾時、finish_reason 對照表沿用同一套（見檔頭「未經同等程度覆核」的既有註記，
        本方法一樣適用）。"""
        api_key = ai_config.get_gemini_api_key()
        if not api_key:
            raise AIProviderMisconfiguredException("GEMINI_API_KEY 未設定")

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise AIProviderMisconfiguredException("google-genai 套件未安裝") from exc

        model = model or ai_config.get_gemini_model()
        max_tokens = ai_config.get_max_output_tokens()
        timeout_sec = ai_config.get_request_timeout_sec()

        client = genai.Client(api_key=api_key)
        started = time.monotonic()
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=[user_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=max_tokens,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    http_options=types.HttpOptions(timeout=timeout_sec * 1000),  # ms
                ),
            )
        except Exception as exc:  # noqa: BLE001 — 見檔頭註記：Gemini 例外階層待實測覆核
            raise _classify_gemini_error(exc) from exc
        finally:
            elapsed_ms = int((time.monotonic() - started) * 1000)

        candidate = response.candidates[0] if getattr(response, "candidates", None) else None
        raw_finish_reason = getattr(candidate, "finish_reason", None)
        finish_reason = getattr(raw_finish_reason, "name", None) or (str(raw_finish_reason) if raw_finish_reason else "")
        stop_reason = _FINISH_REASON_MAP.get(finish_reason, finish_reason.lower() or None)
        truncated = stop_reason == "max_tokens"

        parsed = getattr(response, "parsed", None)

        usage = getattr(response, "usage_metadata", None)
        return ExtractionResult(
            data=parsed,
            model=model,
            stop_reason=stop_reason,
            truncated=truncated,
            input_tokens=getattr(usage, "prompt_token_count", None) if usage else None,
            output_tokens=getattr(usage, "candidates_token_count", None) if usage else None,
            provider_request_id=None,
            response_meta={"elapsed_ms": elapsed_ms, "finish_reason": finish_reason},
        )

    async def research_grounded(
        self, system_prompt: str, user_prompt: str, model: str | None = None, timeout_sec: int | None = None,
    ) -> ResearchResult:
        """開 Google Search grounding 工具做「研究」（見 ADR-IC-17 兩段式萃取 Stage A）。
        **不**傳 response_schema／response_mime_type——grounding 工具與結構化輸出兩者本來就不
        會在同一次呼叫混用，兩段式設計本身就是為了避開兩者併用的相容性風險（規格書 §4.7.7）。

        SDK 呼叫介面已對照本機安裝的 google-genai==2.20.0 原始碼核對過（非僅憑文件記憶）：
        `types.Tool(google_search=types.GoogleSearch())`；引用來源在
        `response.candidates[0].grounding_metadata.grounding_chunks[i].web.uri/.title`；
        查詢次數為 `grounding_metadata.web_search_queries` 的長度。"""
        api_key = ai_config.get_gemini_api_key()
        if not api_key:
            raise AIProviderMisconfiguredException("GEMINI_API_KEY 未設定")

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise AIProviderMisconfiguredException("google-genai 套件未安裝") from exc

        model = model or ai_config.get_gemini_model()
        max_tokens = ai_config.get_max_output_tokens()
        timeout_sec = timeout_sec or ai_config.get_request_timeout_sec()

        client = genai.Client(api_key=api_key)
        started = time.monotonic()
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=[user_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=max_tokens,
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    http_options=types.HttpOptions(timeout=timeout_sec * 1000),  # ms
                ),
            )
        except Exception as exc:  # noqa: BLE001 — 見檔頭註記：Gemini 例外階層待實測覆核
            raise _classify_gemini_error(exc) from exc
        finally:
            elapsed_ms = int((time.monotonic() - started) * 1000)

        candidate = response.candidates[0] if getattr(response, "candidates", None) else None
        raw_finish_reason = getattr(candidate, "finish_reason", None)
        finish_reason = getattr(raw_finish_reason, "name", None) or (str(raw_finish_reason) if raw_finish_reason else "")
        stop_reason = _FINISH_REASON_MAP.get(finish_reason, finish_reason.lower() or None)
        truncated = stop_reason == "max_tokens"

        grounding = getattr(candidate, "grounding_metadata", None)
        citations: list[dict[str, str]] = []
        for chunk in getattr(grounding, "grounding_chunks", None) or []:
            web = getattr(chunk, "web", None)
            uri = getattr(web, "uri", None) if web else None
            if uri:
                citations.append({"url": uri, "title": getattr(web, "title", None) or ""})
        query_count = len(getattr(grounding, "web_search_queries", None) or []) or None

        usage = getattr(response, "usage_metadata", None)
        return ResearchResult(
            text=getattr(response, "text", None) or "",
            citations=citations,
            model=model,
            query_count=query_count,
            stop_reason=stop_reason,
            truncated=truncated,
            input_tokens=getattr(usage, "prompt_token_count", None) if usage else None,
            output_tokens=getattr(usage, "candidates_token_count", None) if usage else None,
            provider_request_id=None,
            response_meta={"elapsed_ms": elapsed_ms, "finish_reason": finish_reason},
        )


def _b64_to_bytes(image_base64: str) -> bytes:
    import base64
    return base64.b64decode(image_base64)


def _classify_gemini_error(exc: Exception) -> Exception:
    """把 google-genai 例外正規化為 ai/errors.py 型別。目前以訊息／狀態碼粗分類，
    待實測後可換成 google.genai.errors 的具體例外類別（見檔頭註記）。"""
    status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    message = str(exc)

    if status_code in (401, 403) or "API key" in message or "PERMISSION_DENIED" in message:
        return AIProviderMisconfiguredException(f"Gemini API 金鑰無效：{message}")
    if status_code == 429 or "RESOURCE_EXHAUSTED" in message:
        return AIRateLimitedException(f"Gemini API 已達限流上限：{message}")
    if "timeout" in message.lower() or "deadline" in message.lower():
        return AITimeoutException(f"Gemini API 呼叫逾時：{message}")
    if status_code in (502, 503, 504) or "Connection" in message:
        return AIProviderUnreachableException(f"無法連線至 Gemini API：{message}")
    return AIProviderError(f"Gemini API 錯誤：{message}")
