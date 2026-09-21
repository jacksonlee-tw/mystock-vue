"""投資筆記 AI 解析編排：閘門 → 記帳（pending）→ 呼叫 LLM → 校驗代號 → 回傳「提案」。

**不寫入筆記**：回傳的只是提案，由使用者在前端逐項勾選後，走既有 PATCH /investment-notes/{id}
落地（先預覽再確認）。成本記在 ai_llm_execution（view_id=investment_note_ai），symbol／market／
trade_date 皆 None——這次呼叫不對應單一個股，比照 services/news_sentiment.py 與 industry_chain 先例。

交易紀律沿用 ai_analysis.py／news_sentiment.py：呼叫 LLM 前先寫 pending 並 commit（中止也留下
紀錄），LLM 的 10～90 秒期間不持有資料庫連線；LLM 之後的收尾寫入失敗只記日誌，不讓已付費的
結果因為寫 log 失敗而回傳錯誤。
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ai import config as ai_config
from ai import guard as ai_guard
from ai.cost import estimate_cost
from ai.errors import (
    AIDisabledException, AIImageTooLargeException, AIInvalidRequestException,
    AIProviderError, AIQuotaExceededException, AIStorageUnavailableException,
)
from ai.providers import get_provider
from ai.providers.base import ExtractionResult
from ai.schema import sections_to_markdown
from core.markdown_images import EmbeddedImage, split_embedded_images
from db.session import get_async_session
from note_ai.prompt import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from note_ai.schema import NoteExtraction, normalize_topic_tags, transcription_to_markdown
from note_ai.validator import validate_symbols
from repositories.activity_log_repository import ActivityLogRepository
from repositories.ai_execution_repository import AIExecutionRepository

logger = logging.getLogger("mystock-backend")

VIEW_ID = "investment_note_ai"
MAX_SUBJECT_LEN = 200


# ── 設定解析 ──────────────────────────────────────────────────────
def resolve_provider(provider_code: Optional[str]) -> str:
    code = (provider_code or ai_config.get_default_provider()).lower()
    if code not in ai_config.VALID_PROVIDERS:
        raise AIInvalidRequestException(f"不支援的 provider：{code}")
    return code


def resolve_model(provider_code: str, requested_model: Optional[str]) -> str:
    """未指定退回該 Provider 的 .env 預設；有指定則必須在白名單內（防止前端傳任意字串打 Provider API）。"""
    if not requested_model:
        return ai_config.get_claude_model() if provider_code == "claude" else ai_config.get_gemini_model()
    if not ai_config.is_valid_model(provider_code, requested_model):
        raise AIInvalidRequestException(f"{provider_code} 不支援的模型：{requested_model}")
    return requested_model


# ── 資料庫存取（模組層小函式，方便測試以 stub 取代）────────────────────
async def _daily_call_count() -> int:
    async with get_async_session() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM ai_llm_execution WHERE view_id = :view_id AND created_at >= CURRENT_DATE"),
            {"view_id": VIEW_ID},
        )
        return result.scalar() or 0


async def get_used_today() -> Optional[int]:
    """今日已用次數；資料庫不可用時回 None（狀態查詢不該因此整個失敗）。"""
    try:
        return await _daily_call_count()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[筆記AI] 查詢今日用量失敗：%s", exc)
        return None


async def _start_execution(*, provider: str, model: str, request_meta: dict) -> int:
    async with get_async_session() as session:
        execution_id = await AIExecutionRepository(session).start(
            report_id=None, provider=provider, model=model,
            symbol=None, market=None, trade_date=None, attempt_no=1,
            prompt_version=PROMPT_VERSION, request_meta=request_meta, view_id=VIEW_ID,
        )
        await session.commit()
        return execution_id


async def _mark_failed(
    execution_id: int, *, error_code: str, error_message: str, result: Optional[ExtractionResult] = None,
) -> None:
    async with get_async_session() as session:
        await AIExecutionRepository(session).mark_failed(
            execution_id, error_code=error_code, error_message=error_message[:500],
            input_tokens=getattr(result, "input_tokens", None), output_tokens=getattr(result, "output_tokens", None),
            stop_reason=getattr(result, "stop_reason", None), response_meta=getattr(result, "response_meta", None),
        )
        await session.commit()


async def _mark_succeeded(
    execution_id: int, *, result: ExtractionResult, estimated_cost_usd: Optional[float],
    image_bytes: int, note_id: int, symbol_count: int,
) -> None:
    async with get_async_session() as session:
        await AIExecutionRepository(session).mark_succeeded(
            execution_id, stop_reason=result.stop_reason, response_meta=result.response_meta,
            provider_request_id=result.provider_request_id,
            input_tokens=result.input_tokens, output_tokens=result.output_tokens,
            cache_read_tokens=None, cache_write_tokens=None, image_bytes=image_bytes,
            estimated_cost_usd=estimated_cost_usd, elapsed_ms=result.response_meta.get("elapsed_ms"),
        )
        await ActivityLogRepository(session).log(
            "NOTE_AI_ANALYZED", view_id=VIEW_ID, success=True, rel_id=execution_id,
            detail=f"筆記 #{note_id}，擷取 {symbol_count} 檔個股",
        )
        await session.commit()


# ── 主流程 ────────────────────────────────────────────────────────
def _check_gates() -> None:
    ai_guard.check_enabled()  # 閘門 0：全站總開關，未啟用時完全不碰 DB／外部 API
    if not ai_config.get_note_ai_enabled():
        raise AIDisabledException("投資筆記 AI 解析未啟用（NOTE_AI_ENABLED=false）")


def _select_images(images: list[EmbeddedImage]) -> tuple[list[EmbeddedImage], int]:
    """套用張數上限與單張大小上限；回傳 (要送的圖, 被略過張數)。大小超限直接拒絕，不默默略過。"""
    cap = ai_config.get_note_ai_max_images()
    sent = images[:cap]
    max_bytes = ai_config.get_max_image_mb() * 1024 * 1024
    for img in sent:
        if len(img.data) > max_bytes:
            raise AIImageTooLargeException(
                f"圖片 {img.ref} 大小約 {len(img.data) / 1024 / 1024:.1f}MB，超過上限 {ai_config.get_max_image_mb()}MB"
            )
    return sent, len(images) - len(sent)


def build_proposal(
    extraction: NoteExtraction, validated_symbols: list, *, sent_refs: set[str],
) -> dict:
    """把 LLM 的結構化輸出整理成給前端預覽的提案。純函式。

    transcriptions 只保留 ref 對得上「實際送出的圖」者——模型自己編出不存在的圖，直接丟掉
    （比照 news_sentiment 的防幻覺作法）；轉錄出空白內容的也丟掉。"""
    transcriptions = []
    for t in extraction.transcriptions:
        markdown = transcription_to_markdown(t)
        if t.ref in sent_refs and markdown:
            transcriptions.append({"ref": t.ref, "kind": t.kind, "title": (t.title or "").strip(), "markdown": markdown})

    return {
        "suggested_subject": (extraction.subject or "").strip()[:MAX_SUBJECT_LEN],
        "topic_tags": normalize_topic_tags(extraction.topic_tags),
        "symbols": [vars(v) for v in validated_symbols],
        "transcriptions": transcriptions,
        "summary_markdown": sections_to_markdown(extraction.summary_sections),
    }


async def analyze_note(note: dict, *, provider_code: Optional[str], model: Optional[str]) -> dict:
    _check_gates()
    provider_code = resolve_provider(provider_code)
    model = resolve_model(provider_code, model)

    found_images, text_only = split_embedded_images(note["content"])
    images, skipped = _select_images(found_images)

    try:
        if await _daily_call_count() >= ai_config.get_note_ai_daily_quota():
            raise AIQuotaExceededException(f"今日投資筆記 AI 解析次數已達上限（{ai_config.get_note_ai_daily_quota()} 次）")
        execution_id = await _start_execution(
            provider=provider_code, model=model,
            request_meta={"note_id": note["id"], "image_count": len(images), "skipped_images": skipped},
        )
    except SQLAlchemyError as exc:
        raise AIStorageUnavailableException("AI 執行紀錄資料庫目前無法使用") from exc

    user_prompt = build_user_prompt(
        note_date=str(note["note_date"]), subject=note["subject"], market=note.get("market"),
        symbol=note.get("symbol"), text=text_only, image_refs=[i.ref for i in images], skipped_image_count=skipped,
    )

    try:
        result = await get_provider(provider_code).extract_structured_multimodal(
            SYSTEM_PROMPT, user_prompt, NoteExtraction, images=images, model=model,
        )
    except Exception as exc:
        await _mark_failed_safely(execution_id, error_code=type(exc).__name__, error_message=str(exc))
        raise

    if result.data is None:
        await _mark_failed_safely(
            execution_id, error_code="NOTE_AI_NO_PARSED_OUTPUT",
            error_message="LLM 回應無法解析為結構化輸出", result=result,
        )
        raise AIProviderError("AI 回應無法解析為結構化輸出，請稍後重試或換一個模型")

    validated = await validate_symbols(result.data.symbols)
    proposal = build_proposal(result.data, validated, sent_refs={i.ref for i in images})

    cost = estimate_cost(result.model or model, result.input_tokens, result.output_tokens)
    try:
        await _mark_succeeded(
            execution_id, result=result, estimated_cost_usd=cost,
            image_bytes=sum(len(i.data) for i in images), note_id=note["id"], symbol_count=len(validated),
        )
    except Exception:  # noqa: BLE001 — 已經付費取得結果，收尾記帳失敗不可讓使用者拿不到
        logger.exception("[筆記AI] 成功收尾寫入資料庫失敗（已略過）")

    proposal.update({
        "note_id": note["id"],
        "provider": provider_code,
        "model": result.model or model,
        "prompt_version": PROMPT_VERSION,
        "execution_id": execution_id,
        "truncated": bool(result.truncated),
        "images": {"sent": len(images), "found": len(found_images), "skipped": skipped},
        "usage": {
            "input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
            "estimated_cost_usd": cost,
        },
    })
    return proposal


async def _mark_failed_safely(execution_id: int, **kwargs) -> None:
    try:
        await _mark_failed(execution_id, **kwargs)
    except Exception:  # noqa: BLE001 — 失敗收尾寫入本身再失敗，不可蓋掉原本要往上拋的例外
        logger.exception("[筆記AI] 失敗收尾寫入資料庫時再度失敗（已略過）")
