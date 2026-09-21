import base64
import unittest
from unittest.mock import AsyncMock, patch

from ai.errors import (
    AIDisabledException, AIImageTooLargeException, AIInvalidRequestException,
    AIProviderError, AIQuotaExceededException,
)
from ai.providers.base import ExtractionResult
from note_ai import analyzer
from note_ai.schema import ExtractedSymbol, ImageTranscription, NoteExtraction
from note_ai.validator import ValidatedSymbol
from ai.schema import ReportSection

WEBP_B64 = base64.b64encode(b"RIFF-fake-webp").decode()


def _note(content=None, **kw):
    note = {
        "id": 7, "note_date": "2026-09-20", "subject": "黃勳喊話", "market": None, "symbol": None,
        "content": content if content is not None else f"![貼上圖片 1][image-1]\n\n[image-1]: data:image/webp;base64,{WEBP_B64}\n",
    }
    note.update(kw)
    return note


def _extraction(**kw):
    base = dict(
        subject="15檔晶片股", topic_tags=["#晶片", "晶片", "法人買超"],
        symbols=[ExtractedSymbol(market="tw", symbol="2303", name="聯電", evidence="image-1 第1列")],
        transcriptions=[
            ImageTranscription(ref="image-1", kind="table", columns=["代號", "公司"], rows=[["2303", "聯電"]]),
            ImageTranscription(ref="image-99", kind="text", text="模型編出來的圖"),
        ],
        summary_sections=[ReportSection(title="重點", body="聯電漲 5.76%")],
    )
    base.update(kw)
    return NoteExtraction(**base)


class StubProvider:
    def __init__(self, data=None, exc=None, truncated=False):
        self.data, self.exc, self.truncated, self.calls = data, exc, truncated, []

    async def extract_structured_multimodal(self, system_prompt, user_prompt, response_schema, images=None, model=None):
        self.calls.append(dict(system=system_prompt, user=user_prompt, schema=response_schema, images=images, model=model))
        if self.exc:
            raise self.exc
        return ExtractionResult(
            data=self.data, model=model, stop_reason="end_turn", truncated=self.truncated,
            input_tokens=1000, output_tokens=500, response_meta={"elapsed_ms": 12},
        )


async def _verified(symbols, **_):
    return [ValidatedSymbol(market=s.market, symbol=s.symbol, name=s.name, evidence=s.evidence,
                            status="verified", master_name=s.name) for s in symbols]


class AnalyzeNoteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mocks = {
            "_daily_call_count": AsyncMock(return_value=0),
            "_start_execution": AsyncMock(return_value=42),
            "_mark_failed": AsyncMock(),
            "_mark_succeeded": AsyncMock(),
        }
        patch.multiple("note_ai.analyzer", validate_symbols=_verified, **self.mocks).start()
        self.p_master = patch("note_ai.analyzer.ai_guard.check_enabled")
        self.p_master.start()
        self.p_note = patch("note_ai.analyzer.ai_config.get_note_ai_enabled", return_value=True)
        self.p_note.start()
        self.p_quota = patch("note_ai.analyzer.ai_config.get_note_ai_daily_quota", return_value=20)
        self.p_quota.start()
        self.p_max = patch("note_ai.analyzer.ai_config.get_note_ai_max_images", return_value=4)
        self.p_max.start()
        self.addCleanup(patch.stopall)

    async def _run(self, provider=None, note=None, **kw):
        provider = provider or StubProvider(_extraction())
        with patch("note_ai.analyzer.get_provider", return_value=provider):
            result = await analyzer.analyze_note(note or _note(), provider_code="gemini", model=None, **kw)
        return result, provider

    async def test_base64_never_reaches_the_prompt_but_the_image_is_sent_as_a_part(self):
        _, provider = await self._run()
        call = provider.calls[0]
        self.assertNotIn("base64", call["user"])
        self.assertNotIn(WEBP_B64, call["user"])
        self.assertEqual([(i.ref, i.mime_type) for i in call["images"]], [("image-1", "image/webp")])
        self.assertIs(call["schema"], NoteExtraction)

    async def test_execution_is_recorded_before_the_llm_call_and_succeeds_afterwards(self):
        order = []
        self.mocks["_start_execution"].side_effect = lambda *a, **k: order.append("start") or 42

        class Ordered(StubProvider):
            async def extract_structured_multimodal(s, *a, **k):
                order.append("call")
                return await super().extract_structured_multimodal(*a, **k)

        await self._run(provider=Ordered(_extraction()))
        self.assertEqual(order[:2], ["start", "call"])
        self.mocks["_mark_succeeded"].assert_awaited_once()
        self.mocks["_mark_failed"].assert_not_awaited()

    async def test_execution_row_carries_no_symbol_and_note_metadata_only(self):
        await self._run()
        kwargs = self.mocks["_start_execution"].await_args.kwargs
        self.assertEqual(kwargs["request_meta"]["note_id"], 7)
        self.assertEqual(kwargs["request_meta"]["image_count"], 1)
        self.assertNotIn("content", kwargs["request_meta"])

    async def test_provider_failure_is_recorded_and_reraised(self):
        boom = AIProviderError("上游 502")
        with self.assertRaises(AIProviderError):
            await self._run(provider=StubProvider(exc=boom))
        self.mocks["_mark_failed"].assert_awaited_once()
        self.assertEqual(self.mocks["_mark_failed"].await_args.args[0], 42)
        self.mocks["_mark_succeeded"].assert_not_awaited()

    async def test_unparseable_output_is_a_recorded_failure(self):
        with self.assertRaises(AIProviderError):
            await self._run(provider=StubProvider(data=None))
        self.assertEqual(self.mocks["_mark_failed"].await_args.kwargs["error_code"], "NOTE_AI_NO_PARSED_OUTPUT")

    async def test_proposal_never_writes_the_note_and_contains_normalized_suggestions(self):
        result, _ = await self._run()
        self.assertEqual(result["suggested_subject"], "15檔晶片股")
        self.assertEqual(result["topic_tags"], ["晶片", "法人買超"])
        self.assertEqual([s["symbol"] for s in result["symbols"]], ["2303"])
        self.assertEqual(result["symbols"][0]["status"], "verified")
        self.assertEqual(result["summary_markdown"], "### 重點\n\n聯電漲 5.76%")

    async def test_transcriptions_for_unknown_image_refs_are_dropped(self):
        result, _ = await self._run()
        self.assertEqual([t["ref"] for t in result["transcriptions"]], ["image-1"])
        self.assertIn("| 2303 | 聯電 |", result["transcriptions"][0]["markdown"])

    async def test_images_over_the_cap_are_skipped_and_reported(self):
        defs = "\n\n".join(f"[image-{n}]: data:image/webp;base64,{WEBP_B64}" for n in range(1, 4))
        with patch("note_ai.analyzer.ai_config.get_note_ai_max_images", return_value=2):
            result, provider = await self._run(note=_note(content=f"內文\n\n{defs}\n"))
        self.assertEqual(len(provider.calls[0]["images"]), 2)
        self.assertEqual(result["images"], {"sent": 2, "found": 3, "skipped": 1})
        self.assertIn("未附上", provider.calls[0]["user"])

    async def test_text_only_note_is_analyzed_without_images(self):
        result, provider = await self._run(note=_note(content="純文字筆記"), provider=StubProvider(_extraction(transcriptions=[])))
        self.assertEqual(provider.calls[0]["images"], [])
        self.assertEqual(result["images"]["sent"], 0)

    async def test_usage_and_cost_are_reported(self):
        result, _ = await self._run()
        self.assertEqual(result["usage"]["input_tokens"], 1000)
        self.assertEqual(result["execution_id"], 42)
        self.assertIn("estimated_cost_usd", result["usage"])

    async def test_truncated_output_is_flagged(self):
        result, _ = await self._run(provider=StubProvider(_extraction(), truncated=True))
        self.assertTrue(result["truncated"])

    async def test_success_bookkeeping_failure_does_not_lose_the_paid_result(self):
        self.mocks["_mark_succeeded"].side_effect = RuntimeError("db gone")
        result, _ = await self._run()
        self.assertEqual(result["suggested_subject"], "15檔晶片股")

    # ── 閘門 ───────────────────────────────────────────────────
    async def test_disabled_flag_blocks_before_touching_db_or_provider(self):
        with patch("note_ai.analyzer.ai_config.get_note_ai_enabled", return_value=False):
            provider = StubProvider(_extraction())
            with patch("note_ai.analyzer.get_provider", return_value=provider):
                with self.assertRaises(AIDisabledException):
                    await analyzer.analyze_note(_note(), provider_code="gemini", model=None)
        self.mocks["_daily_call_count"].assert_not_awaited()
        self.assertEqual(provider.calls, [])

    async def test_quota_exhausted_blocks_before_calling_the_provider(self):
        self.mocks["_daily_call_count"].return_value = 20
        provider = StubProvider(_extraction())
        with self.assertRaises(AIQuotaExceededException):
            await self._run(provider=provider)
        self.assertEqual(provider.calls, [])
        self.mocks["_start_execution"].assert_not_awaited()

    async def test_unknown_model_is_rejected_before_any_cost(self):
        provider = StubProvider(_extraction())
        with patch("note_ai.analyzer.get_provider", return_value=provider):
            with self.assertRaises(AIInvalidRequestException):
                await analyzer.analyze_note(_note(), provider_code="gemini", model="gpt-9")
        self.assertEqual(provider.calls, [])

    async def test_unknown_provider_is_rejected(self):
        with self.assertRaises(AIInvalidRequestException):
            await analyzer.analyze_note(_note(), provider_code="openai", model=None)

    async def test_oversized_image_is_rejected_before_any_cost(self):
        big = base64.b64encode(b"x" * (5 * 1024 * 1024)).decode()
        note = _note(content=f"[image-1]: data:image/webp;base64,{big}\n")
        with patch("note_ai.analyzer.ai_config.get_max_image_mb", return_value=4):
            with self.assertRaises(AIImageTooLargeException):
                await self._run(note=note)
        self.mocks["_start_execution"].assert_not_awaited()


class DefaultsTests(unittest.TestCase):
    def test_resolve_model_falls_back_to_provider_default_from_env(self):
        with patch("note_ai.analyzer.ai_config.get_gemini_model", return_value="gemini-3.6-flash"):
            self.assertEqual(analyzer.resolve_model("gemini", None), "gemini-3.6-flash")


if __name__ == "__main__":
    unittest.main()
