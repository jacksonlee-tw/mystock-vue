"""
ai/providers/claude_provider.py
Claude（Anthropic）Provider 實作（見規格書 §4.3）。

關鍵實作要點（皆為初版構想 v1.0 未涵蓋或寫錯之處，見規格書 §0.1 D-01～D-05）：
- 客戶端延遲建立（ADR-AI-05）：未設定 CLAUDE_API_KEY 時，只有真的呼叫 analyze() 才會出錯，
  模組匯入與服務啟動完全不受影響。
- `anthropic` 套件本身也延遲到 analyze() 內才 import（AC-AI-02）：本檔在 main.py 匯入路由的
  過程中就會被 ai/providers/__init__.py 一併載入，若在模組頂層 `import anthropic`，未安裝
  該套件的環境會連服務都啟動不了——即使 AI_ANALYSIS_ENABLED=false 也一樣，因為匯入發生在
  「讀到這個旗標」之前。比照 gemini_provider.py 的作法。
- 使用 AsyncAnthropic（ADR-AI-04），不得用同步客戶端卡住 event loop。
- max_tokens 走設定（AI_MAX_OUTPUT_TOKENS，預設 8000），避免 D-05 那種被截斷的報告。
- 結構化輸出用 client.messages.parse(output_format=AnalysisReport)（ADR-AI-06）。
- 不顯式傳 thinking 參數：Claude Sonnet 5／Opus 5 省略 thinking 時即以 adaptive 模式執行，
  顯式指定反而在與結構化輸出併用時徒增不確定性。
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


@ai_provider(code="claude", display_name="Claude (Anthropic)")
class ClaudeProvider(AIProvider):
    async def analyze(
        self, image_base64: str, system_prompt: str, user_prompt: str, model: str | None = None,
    ) -> AnalysisResult:
        api_key = ai_config.get_claude_api_key()
        if not api_key:
            raise AIProviderMisconfiguredException("CLAUDE_API_KEY 未設定")

        try:
            import anthropic
        except ImportError as exc:
            raise AIProviderMisconfiguredException("anthropic 套件未安裝") from exc

        model = model or ai_config.get_claude_model()
        max_tokens = ai_config.get_max_output_tokens()
        timeout_sec = ai_config.get_request_timeout_sec()

        client = anthropic.AsyncAnthropic(api_key=api_key)
        started = time.monotonic()
        try:
            response = await client.with_options(timeout=timeout_sec).messages.parse(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_base64,
                            },
                        },
                        {"type": "text", "text": user_prompt},
                    ],
                }],
                output_format=LLMAnalysisReport,
            )
        except anthropic.AuthenticationError as exc:
            raise AIProviderMisconfiguredException("Claude API 金鑰無效") from exc
        except anthropic.RateLimitError as exc:
            retry_after = None
            try:
                retry_after = int(exc.response.headers.get("retry-after", "0")) or None
            except Exception:
                pass
            raise AIRateLimitedException("Claude API 已達限流上限", retry_after_sec=retry_after) from exc
        except anthropic.APITimeoutError as exc:
            raise AITimeoutException("Claude API 呼叫逾時") from exc
        except anthropic.APIConnectionError as exc:
            raise AIProviderUnreachableException("無法連線至 Claude API") from exc
        except anthropic.APIStatusError as exc:
            raise AIProviderError(f"Claude API 錯誤（{exc.status_code}）：{exc.message}") from exc
        finally:
            elapsed_ms = int((time.monotonic() - started) * 1000)

        stop_reason = response.stop_reason
        truncated = stop_reason == "max_tokens"

        # refusal：拿不到 parsed_output，改回一個中性報告而非整個request失敗（§4.7 模型拒答不當系統錯誤）
        llm_report: LLMAnalysisReport | None = getattr(response, "parsed_output", None)
        if llm_report is not None:
            parsed = from_llm_report(llm_report)
        else:
            text_fallback = ""
            for block in response.content:
                if getattr(block, "type", None) == "text":
                    text_fallback = block.text
                    break
            parsed = AnalysisReport(
                verdict="neutral",
                headline="AI 未能產生結構化結論" if stop_reason != "refusal" else "AI 婉拒本次分析請求",
                report_markdown=text_fallback or "（無內容）",
                confidence="low",
            )

        usage = response.usage
        return AnalysisResult(
            report=parsed,
            model=response.model,
            stop_reason=stop_reason,
            truncated=truncated,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", None),
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", None),
            provider_request_id=getattr(response, "_request_id", None),
            response_meta={
                "elapsed_ms": elapsed_ms,
                "stop_reason": stop_reason,
            },
        )

    async def extract_structured(
        self, system_prompt: str, user_prompt: str, response_schema: type, model: str | None = None,
    ) -> ExtractionResult:
        """純文字結構化萃取（見 ADR-IC-12）：與 analyze() 幾乎同一套呼叫骨架，差異只有
        ① 沒有圖片 content block、② output_format 是呼叫端傳入的參數而非寫死 LLMAnalysisReport。
        例外分類完全沿用同一套 except 鏈。"""
        api_key = ai_config.get_claude_api_key()
        if not api_key:
            raise AIProviderMisconfiguredException("CLAUDE_API_KEY 未設定")

        try:
            import anthropic
        except ImportError as exc:
            raise AIProviderMisconfiguredException("anthropic 套件未安裝") from exc

        model = model or ai_config.get_claude_model()
        max_tokens = ai_config.get_max_output_tokens()
        timeout_sec = ai_config.get_request_timeout_sec()

        client = anthropic.AsyncAnthropic(api_key=api_key)
        started = time.monotonic()
        try:
            response = await client.with_options(timeout=timeout_sec).messages.parse(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": [{"type": "text", "text": user_prompt}]}],
                output_format=response_schema,
            )
        except anthropic.AuthenticationError as exc:
            raise AIProviderMisconfiguredException("Claude API 金鑰無效") from exc
        except anthropic.RateLimitError as exc:
            retry_after = None
            try:
                retry_after = int(exc.response.headers.get("retry-after", "0")) or None
            except Exception:
                pass
            raise AIRateLimitedException("Claude API 已達限流上限", retry_after_sec=retry_after) from exc
        except anthropic.APITimeoutError as exc:
            raise AITimeoutException("Claude API 呼叫逾時") from exc
        except anthropic.APIConnectionError as exc:
            raise AIProviderUnreachableException("無法連線至 Claude API") from exc
        except anthropic.APIStatusError as exc:
            raise AIProviderError(f"Claude API 錯誤（{exc.status_code}）：{exc.message}") from exc
        finally:
            elapsed_ms = int((time.monotonic() - started) * 1000)

        stop_reason = response.stop_reason
        truncated = stop_reason == "max_tokens"
        parsed = getattr(response, "parsed_output", None)

        usage = response.usage
        return ExtractionResult(
            data=parsed,
            model=response.model,
            stop_reason=stop_reason,
            truncated=truncated,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            provider_request_id=getattr(response, "_request_id", None),
            response_meta={
                "elapsed_ms": elapsed_ms,
                "stop_reason": stop_reason,
            },
        )

    async def research_grounded(
        self, system_prompt: str, user_prompt: str, model: str | None = None, timeout_sec: int | None = None,
    ) -> ResearchResult:
        """開 Claude 內建 web_search 工具做「研究」（見 ADR-IC-17 兩段式萃取 Stage A）。
        **不**用 `.parse()`／`output_format`——工具與結構化輸出兩段式分開呼叫，理由同
        gemini_provider.py 的 research_grounded()。

        SDK 呼叫介面已對照本機安裝的 anthropic==1.2.0 原始碼核對過（非僅憑文件記憶）：
        工具宣告 `{"type": "web_search_20250305", "name": "web_search"}`；回應
        `response.content` 混雜三種 block——`type="text"`（研究敘述）、
        `type="server_tool_use"`（`name="web_search"` 時代表一次查詢）、
        `type="web_search_tool_result"`（`.content` 是 `list[WebSearchResultBlock]` 或一個
        error 物件，需先判斷是不是 list 再迭代取 `.url`/`.title`）。"""
        api_key = ai_config.get_claude_api_key()
        if not api_key:
            raise AIProviderMisconfiguredException("CLAUDE_API_KEY 未設定")

        try:
            import anthropic
        except ImportError as exc:
            raise AIProviderMisconfiguredException("anthropic 套件未安裝") from exc

        model = model or ai_config.get_claude_model()
        max_tokens = ai_config.get_max_output_tokens()
        timeout_sec = timeout_sec or ai_config.get_request_timeout_sec()

        client = anthropic.AsyncAnthropic(api_key=api_key)
        started = time.monotonic()
        try:
            response = await client.with_options(timeout=timeout_sec).messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": [{"type": "text", "text": user_prompt}]}],
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
            )
        except anthropic.AuthenticationError as exc:
            raise AIProviderMisconfiguredException("Claude API 金鑰無效") from exc
        except anthropic.RateLimitError as exc:
            retry_after = None
            try:
                retry_after = int(exc.response.headers.get("retry-after", "0")) or None
            except Exception:
                pass
            raise AIRateLimitedException("Claude API 已達限流上限", retry_after_sec=retry_after) from exc
        except anthropic.APITimeoutError as exc:
            raise AITimeoutException("Claude API 呼叫逾時") from exc
        except anthropic.APIConnectionError as exc:
            raise AIProviderUnreachableException("無法連線至 Claude API") from exc
        except anthropic.APIStatusError as exc:
            raise AIProviderError(f"Claude API 錯誤（{exc.status_code}）：{exc.message}") from exc
        finally:
            elapsed_ms = int((time.monotonic() - started) * 1000)

        text_parts: list[str] = []
        citations: list[dict[str, str]] = []
        query_count = 0
        for block in response.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(block.text)
            elif btype == "server_tool_use" and getattr(block, "name", None) == "web_search":
                query_count += 1
            elif btype == "web_search_tool_result":
                content = block.content if isinstance(block.content, list) else []
                for item in content:
                    url = getattr(item, "url", None)
                    if url:
                        citations.append({"url": url, "title": getattr(item, "title", None) or ""})

        stop_reason = response.stop_reason
        truncated = stop_reason == "max_tokens"
        usage = response.usage
        return ResearchResult(
            text="\n".join(text_parts),
            citations=citations,
            model=response.model,
            query_count=query_count or None,
            stop_reason=stop_reason,
            truncated=truncated,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            provider_request_id=getattr(response, "_request_id", None),
            response_meta={
                "elapsed_ms": elapsed_ms,
                "stop_reason": stop_reason,
            },
        )
