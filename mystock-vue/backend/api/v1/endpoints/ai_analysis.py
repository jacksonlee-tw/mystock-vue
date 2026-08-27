"""
api/v1/endpoints/ai_analysis.py
AI 技術分析報告 API（見 docs/16.AI技術分析/AI技術分析規劃.md §6）。

不掛 require_owner（v3.2 決議，見規格書 §8.1 修訂）：本專案除了通知平台的獨立管理頁面外，
其餘功能（含本模組）一律不要求登入，前端也沒有任何入口能取得 owner 的 Cookie／Token——
掛上去只會是打不開的死路。成本控管改成完全依賴既有的資料庫層防線：
AI_DAILY_QUOTA（全站每日新報告總量）＋ (market_type, symbol, trade_date, provider, model)
唯一鍵（同一標的同一交易日、同一 provider+model 組合只呼叫一次 LLM，ADR-AI-16／ADR-AI-21；
換模型視為另一份獨立報告，可再產生一次，見 v3.4）。
"""
from __future__ import annotations
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from ai import config as ai_config
from ai.errors import (
    AIDisabledException, AIStorageUnavailableException, AIQuotaExceededException,
    AIAnalysisInProgressException, AIProviderMisconfiguredException, AIRateLimitedException,
    AITimeoutException, AIProviderUnreachableException, AIProviderError,
    AIInvalidRequestException, AIImageTooLargeException,
)
from ai import guard
from ai.prompt import SYSTEM_PROMPT, build_user_prompt
from ai.providers import get_provider, PROVIDER_REGISTRY
from ai.recorder import AIRecorder
from ai.summary import build_quant_summary
from core.exceptions import SymbolNotFoundException
from db.session import get_db, get_async_session
from repositories.ai_execution_repository import AIExecutionRepository
from repositories.ai_report_repository import AIReportRepository
from repositories.activity_log_repository import ActivityLogRepository

logger = logging.getLogger("mystock-backend")

router = APIRouter(
    prefix="/api/v1/ai",
    tags=["AI Analysis"],
)

DISCLAIMER = "本報告由 AI 依技術面資料生成，僅供參考，不構成投資建議；投資決策風險請自負。"


class AnalyzeStockRequest(BaseModel):
    symbol: str
    market: str = "tw"
    period: str = "daily"
    months: int = 3
    provider: Optional[str] = None
    model: Optional[str] = None  # 未帶時退回該 provider 的 .env 預設模型（v3.4，見 §4.3）
    image_base64: str
    force: bool = False


# ── 共用小工具 ──────────────────────────────────────────────────
def _validate_image_size(image_base64: str) -> int:
    approx_bytes = int(len(image_base64) * 3 / 4)
    max_bytes = ai_config.get_max_image_mb() * 1024 * 1024
    if approx_bytes > max_bytes:
        raise AIImageTooLargeException(
            f"圖片大小約 {approx_bytes / 1024 / 1024:.1f}MB，超過上限 {ai_config.get_max_image_mb()}MB"
        )
    return approx_bytes


def _default_model_for(provider_code: str) -> str:
    if provider_code == "claude":
        return ai_config.get_claude_model()
    if provider_code == "gemini":
        return ai_config.get_gemini_model()
    return provider_code


def _resolve_model(provider_code: str, requested_model: Optional[str]) -> str:
    """未指定模型時退回該 Provider 的 .env 預設；有指定則必須在白名單內（v3.4，防止
    前端傳任意字串直接打 Provider API，見 ai_config.SELECTABLE_MODELS 的設計說明）。"""
    if not requested_model:
        return _default_model_for(provider_code)
    if not ai_config.is_valid_model(provider_code, requested_model):
        raise AIInvalidRequestException(f"{provider_code} 不支援的模型：{requested_model}")
    return requested_model


def _estimate_cost(model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    pricing = ai_config.get_model_pricing(model)
    if not pricing or input_tokens is None or output_tokens is None:
        return None
    return round(input_tokens / 1_000_000 * pricing["input"] + output_tokens / 1_000_000 * pricing["output"], 6)


_ERROR_CODE_MAP = {
    AIProviderMisconfiguredException: "AI_PROVIDER_MISCONFIGURED",
    AIRateLimitedException: "AI_RATE_LIMITED",
    AITimeoutException: "AI_TIMEOUT",
    AIProviderUnreachableException: "AI_PROVIDER_UNREACHABLE",
    AIProviderError: "AI_PROVIDER_ERROR",
}


def _error_code_for(exc: Exception) -> str:
    for cls, code in _ERROR_CODE_MAP.items():
        if isinstance(exc, cls):
            return code
    return "AI_UNKNOWN_ERROR"


def _report_envelope(row: dict, cached: bool | None = None) -> dict:
    data = {
        "id": row["id"],
        "symbol": row["symbol"],
        "stock_name": row.get("stock_name"),
        "market": row["market_type"],
        "trade_date": _iso(row["trade_date"]),
        "status": row["status"],
        "verdict": row.get("verdict"),
        "headline": row.get("headline"),
        "support_levels": row.get("support_levels") or [],
        "resistance_levels": row.get("resistance_levels") or [],
        "stop_loss": row.get("stop_loss"),
        "confidence": row.get("confidence"),
        "truncated": row.get("truncated", False),
        "provider": row.get("provider"),
        "model": row.get("model"),
        "chart": {
            "period": row.get("chart_period"),
            "months": row.get("chart_months"),
            "start_date": _iso(row.get("chart_start_date")),
            "end_date": _iso(row.get("chart_end_date")),
        },
        "generated_at": _iso(row.get("generated_at")),
        "disclaimer": DISCLAIMER,
    }
    if "report_markdown" in row:
        data["report_markdown"] = row.get("report_markdown")
    if row.get("status") == "failed":
        data["error_code"] = row.get("error_code")
    if cached is not None:
        data["cached"] = cached
    return {"success": True, "data": data}


def _iso(value):
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


# ── 產生報告（§6.1）─────────────────────────────────────────────
@router.post("/analyze-stock", summary="產生（或回讀當日既有）AI 技術分析報告")
async def analyze_stock(req: AnalyzeStockRequest):
    guard.check_enabled()  # 閘門 0：未啟用時完全不碰 DB／外部 API（AC-AI-01）

    provider_code = (req.provider or ai_config.get_default_provider()).lower()
    if provider_code not in ai_config.VALID_PROVIDERS:
        raise AIInvalidRequestException(f"不支援的 provider：{provider_code}")
    model = _resolve_model(provider_code, req.model)  # 佔位、紀錄、實際呼叫三處都用這同一個字串

    image_bytes_len = _validate_image_size(req.image_base64)

    qs = await build_quant_summary(req.symbol, req.market, req.period, req.months)
    if qs is None:
        raise SymbolNotFoundException(f"找不到 {req.market}/{req.symbol} 的行情資料")

    # 第一階段交易：取得執行權（閘門 2～5）＋ 佔位寫入 pending 執行紀錄，隨即 commit，
    # 不在呼叫 LLM 的 10～90 秒期間持有資料庫連線／交易（規格書 §5.7）。
    try:
        async with get_async_session() as session:
            decision = await guard.resolve_report_slot(
                session, symbol=req.symbol, market=req.market, trade_date=qs.trade_date,
                provider=provider_code, model=model, stock_name=qs.stock_name,
                chart_period=req.period, chart_months=req.months,
                chart_start_date=qs.chart_start_date, chart_end_date=qs.chart_end_date,
                force=req.force,
            )
            recorder = AIRecorder(session)

            if decision.outcome == "cached":
                await recorder.log_cached(view_id="stock_dashboard", report_id=decision.report["id"])
                await session.commit()
                return _report_envelope(decision.report, cached=True)

            execution_id = await recorder.start_execution(
                report_id=decision.report_id, provider=provider_code, model=model,
                symbol=req.symbol, market=req.market, trade_date=qs.trade_date,
                attempt_no=decision.attempt_no, prompt_version=ai_config.get_prompt_version(),
                request_meta={
                    "max_tokens": ai_config.get_max_output_tokens(),
                    "image_bytes": image_bytes_len,
                    "chart_period": req.period, "chart_months": req.months,
                },
                is_dry_run=decision.forced,
            )
            await session.commit()
            report_id = decision.report_id
    except (AIQuotaExceededException, AIAnalysisInProgressException):
        raise
    except SQLAlchemyError as exc:
        raise AIStorageUnavailableException("AI 報告資料庫目前無法使用") from exc

    # 呼叫 LLM（不持有 DB 交易）
    provider_impl = get_provider(provider_code)
    user_prompt = build_user_prompt(req.symbol, qs.stock_name, req.market, qs.summary)

    try:
        result = await provider_impl.analyze(req.image_base64, SYSTEM_PROMPT, user_prompt, model=model)
    except Exception as exc:
        error_code = _error_code_for(exc)
        try:
            async with get_async_session() as fail_session:
                await AIRecorder(fail_session).record_failure(
                    execution_id=execution_id, report_id=report_id, view_id="stock_dashboard",
                    error_code=error_code, error_message=str(exc),
                )
                await fail_session.commit()
        except Exception:
            logger.exception("[AI] 失敗收尾寫入資料庫時再度失敗（已略過）")
        raise

    # 第二階段交易：成功收尾，執行紀錄與報告內容在同一交易內更新（§5.7）
    est_cost = _estimate_cost(result.model, result.input_tokens, result.output_tokens)
    report_data = {
        "provider": provider_code,
        "model": result.model,
        "verdict": result.report.verdict,
        "headline": result.report.headline,
        "support_levels": [lvl.model_dump() for lvl in result.report.support_levels],
        "resistance_levels": [lvl.model_dump() for lvl in result.report.resistance_levels],
        "stop_loss": result.report.stop_loss,
        "report_markdown": result.report.report_markdown,
        "confidence": result.report.confidence,
        "quant_summary": qs.summary,
        "truncated": result.truncated,
    }
    async with get_async_session() as session2:
        await AIRecorder(session2).record_success(
            execution_id=execution_id, report_id=report_id, view_id="stock_dashboard",
            stop_reason=result.stop_reason, response_meta=result.response_meta,
            provider_request_id=result.provider_request_id,
            input_tokens=result.input_tokens, output_tokens=result.output_tokens,
            cache_read_tokens=result.cache_read_tokens, cache_write_tokens=result.cache_write_tokens,
            image_bytes=image_bytes_len, estimated_cost_usd=est_cost,
            elapsed_ms=result.response_meta.get("elapsed_ms"),
            report_data=report_data,
        )
        await session2.commit()
        final_row = await AIReportRepository(session2).get_by_id(report_id)

    return _report_envelope(final_row, cached=False)


@router.get("/models", summary="可選模型清單（供產生報告前的選單使用，v3.4）")
async def list_models():
    return {
        "success": True,
        "data": {
            "default_provider": ai_config.get_default_provider(),
            "providers": {
                code: {
                    "display_name": PROVIDER_REGISTRY[code].display_name,
                    "default_model": _default_model_for(code),
                    "models": ai_config.get_selectable_models(code),
                }
                for code in ai_config.VALID_PROVIDERS
            },
        },
    }


@router.get("/status", summary="AI 功能狀態、今日用量與配額")
async def ai_status(db=Depends(get_db)):
    exec_repo = AIExecutionRepository(db)
    report_repo = AIReportRepository(db)
    today = date.today()
    totals = await exec_repo.get_usage_totals(date_from=today, date_to=today)
    today_report_count = await report_repo.count_succeeded_today()
    return {
        "success": True,
        "data": {
            "enabled": ai_config.is_enabled(),
            "default_provider": ai_config.get_default_provider(),
            "providers": list(PROVIDER_REGISTRY.keys()),
            "daily_quota": ai_config.get_daily_quota(),
            "today_report_count": today_report_count,
            "today_usage": totals,
        },
    }


# ── 歷史報告查詢（§6.2）─────────────────────────────────────────
@router.get("/reports", summary="歷史報告列表（分頁）")
async def list_reports(
    market: Optional[str] = None, symbol: Optional[str] = None,
    date_from: Optional[date] = None, date_to: Optional[date] = None,
    verdict: Optional[str] = None, status: str = "succeeded",
    limit: int = Query(20, le=100), offset: int = 0,
    db=Depends(get_db),
):
    repo = AIReportRepository(db)
    rows, total = await repo.list_reports(
        market=market, symbol=symbol, date_from=date_from, date_to=date_to,
        verdict=verdict, status=status, limit=limit, offset=offset,
    )
    for row in rows:
        row["trade_date"] = _iso(row.get("trade_date"))
        row["chart_start_date"] = _iso(row.get("chart_start_date"))
        row["chart_end_date"] = _iso(row.get("chart_end_date"))
        row["generated_at"] = _iso(row.get("generated_at"))
        row["updated_at"] = _iso(row.get("updated_at"))
    await AIRecorder(db).log_query(view_id="ai_report_history", comments=f"market={market} symbol={symbol}")
    await db.commit()
    return {"success": True, "data": {"items": rows, "total": total, "limit": limit, "offset": offset}}


@router.get("/reports/latest", summary="查詢某標的（可選：特定 provider+model）最近一筆成功報告")
async def get_latest_report(
    market: str, symbol: str,
    provider: Optional[str] = None, model: Optional[str] = None,
    db=Depends(get_db),
):
    """v3.4：帶 provider+model 時精確判斷「這個模型組合今天是否已產生」（§7.3 按鈕文案判斷）；
    不帶則回該標的最近一筆（任何 provider/model），供舊版呼叫端相容。"""
    repo = AIReportRepository(db)
    rows, _ = await repo.list_reports(
        market=market, symbol=symbol, provider=provider, model=model,
        status="succeeded", limit=1, offset=0,
    )
    if not rows:
        return {"success": True, "data": None}
    return _report_envelope(rows[0])


@router.get("/reports/{report_id}", summary="單筆報告完整內容")
async def get_report(report_id: int, db=Depends(get_db)):
    repo = AIReportRepository(db)
    row = await repo.get_by_id(report_id)
    if not row:
        raise SymbolNotFoundException(f"找不到報告 id={report_id}")
    await AIRecorder(db).log_view(view_id="ai_report_history", report_id=report_id)
    await db.commit()
    return _report_envelope(row)


@router.delete("/reports/{report_id}", summary="刪除單筆報告")
async def delete_report(report_id: int, db=Depends(get_db)):
    repo = AIReportRepository(db)
    deleted = await repo.delete_report(report_id)
    await AIRecorder(db).log_delete(view_id="ai_report_history", report_id=report_id, success=deleted)
    if not deleted:
        raise SymbolNotFoundException(f"找不到報告 id={report_id}")
    await db.commit()
    return {"success": True, "message": "已刪除"}


# ── 執行紀錄與用量查詢（§6.3）───────────────────────────────────
@router.get("/executions", summary="LLM 呼叫執行紀錄列表（含失敗）")
async def list_executions(
    provider: Optional[str] = None, model: Optional[str] = None, status: Optional[str] = None,
    symbol: Optional[str] = None, market: Optional[str] = None,
    date_from: Optional[date] = None, date_to: Optional[date] = None,
    include_dry_run: bool = False, limit: int = Query(20, le=100), offset: int = 0,
    db=Depends(get_db),
):
    repo = AIExecutionRepository(db)
    rows, total = await repo.list_executions(
        provider=provider, model=model, status=status, symbol=symbol, market=market,
        date_from=date_from, date_to=date_to, include_dry_run=include_dry_run,
        limit=limit, offset=offset,
    )
    for row in rows:
        for key in ("trade_date", "started_at", "completed_at", "created_at"):
            row[key] = _iso(row.get(key))
        row["execution_uuid"] = str(row["execution_uuid"]) if row.get("execution_uuid") else None
    return {"success": True, "data": {"items": rows, "total": total, "limit": limit, "offset": offset}}


@router.get("/usage", summary="用量與成本彙總")
async def get_usage(
    group_by: str = Query("model", pattern="^(model|symbol|day)$"),
    date_from: Optional[date] = None, date_to: Optional[date] = None,
    db=Depends(get_db),
):
    exec_repo = AIExecutionRepository(db)
    totals = await exec_repo.get_usage_totals(date_from=date_from, date_to=date_to)
    groups = await exec_repo.get_usage_by_group(group_by, date_from=date_from, date_to=date_to)

    log_repo = ActivityLogRepository(db)
    _, cached_count = await log_repo.list_logs(
        code="AI_REPORT_CACHED", date_from=date_from, date_to=date_to, limit=1, offset=0
    )

    for g in groups:
        if isinstance(g.get("key"), (date, datetime)):
            g["key"] = _iso(g["key"])

    return {
        "success": True,
        "data": {
            "range": {"from": _iso(date_from), "to": _iso(date_to)},
            "totals": {**totals, "cached_hit_count": cached_count},
            "groups": groups,
        },
    }


@router.get("/activity", summary="活動事件紀錄查詢")
async def get_activity(
    code: Optional[str] = None, rel_id: Optional[int] = None,
    date_from: Optional[date] = None, date_to: Optional[date] = None,
    limit: int = Query(50, le=200), offset: int = 0,
    db=Depends(get_db),
):
    repo = ActivityLogRepository(db)
    rows, total = await repo.list_logs(
        code=code, rel_id=rel_id, date_from=date_from, date_to=date_to, limit=limit, offset=offset
    )
    for row in rows:
        row["created_date"] = _iso(row.get("created_date"))
    return {"success": True, "data": {"items": rows, "total": total, "limit": limit, "offset": offset}}
