"""
api/v1/endpoints/ai_batch.py
監控清單批次的設定、費用預估與手動觸發（使用者要求：Phase5 §8 的自動排程批次之外，
另外開一個「隨時手動跑一次」的入口，執行前必須先讓使用者看到預估費用並明確確認）。

掛 require_owner（比照 war_room.py）：會改動全站設定（AI_BATCH_ENABLED）、會實際花錢呼叫
LLM，比讀資料的敏感度更高，不比照 ai_analysis.py 的匿名開放。
"""
from __future__ import annotations
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ai import config as ai_config
from ai.cost import estimate_cost
from ai.errors import AIDisabledException
from core.owner_auth import require_owner
from db.session import get_db
from repositories.ai_execution_repository import AIExecutionRepository
from repositories.ai_report_repository import AIReportRepository

router = APIRouter(
    prefix="/api/v1/ai/batch",
    tags=["AI Analysis - Batch"],
    dependencies=[Depends(require_owner)],
)

# 查無歷史執行資料時的保守估算（純文字批次 prompt，無圖片；見 ai/prompt.py 的
# BATCH_SYSTEM_PROMPT + ai/summary.py 組出的量化摘要典型長度）——只在還沒有任何一次批次
# 實際執行紀錄可供平均時才會用到，之後自動改用真實歷史平均（AIExecutionRepository.
# get_avg_cost_for_model()），不會一直停留在這個粗估值。
_FALLBACK_AVG_INPUT_TOKENS = 2200.0
_FALLBACK_AVG_OUTPUT_TOKENS = 1200.0


def _current_settings() -> dict:
    return {
        "enabled": ai_config.get_batch_enabled(),
        "daily_quota": ai_config.get_batch_daily_quota(),
        "exclude_etf": ai_config.get_batch_exclude_etf(),
        "provider": ai_config.get_batch_provider(),
        "model": ai_config.get_batch_model(),
    }


@router.get("/settings", summary="批次功能目前設定")
def get_settings():
    return {"success": True, "data": _current_settings()}


class BatchSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    daily_quota: Optional[int] = None
    provider: Optional[str] = None
    model: Optional[str] = None


@router.put("/settings", summary="更新批次設定（啟用開關／每日配額／預設 Provider＋模型），存檔後立即生效、不需重啟")
def update_settings(req: BatchSettingsUpdate):
    try:
        ai_config.set_batch_settings(
            enabled=req.enabled, daily_quota=req.daily_quota,
            provider=req.provider, model=req.model,
        )
    except ValueError as e:
        return {"success": False, "error": {"code": "INVALID_BATCH_SETTING", "message": str(e)}}
    return {"success": True, "data": _current_settings()}


@router.get("/estimate", summary="執行前預估費用／token 用量（UI 需先顯示此結果並取得使用者確認才能觸發）")
async def estimate_batch(market: str = "tw", symbols: Optional[str] = None, db=Depends(get_db)):
    from ai.batch_job import get_eligible_symbols

    # symbols：戰情室多選標的手動觸發（逗號分隔，GET query 沒有原生陣列語意，比照前端
    # axios 慣例用逗號字串傳遞）。使用者已明確勾選子集合，略過 ETF 排除規則與監控清單全量
    # 掃描，直接把這份子集合當成候選名單（見 ai/batch_job.py::run_watchlist_batch() 的說明）。
    if symbols:
        eligible = [s.strip() for s in symbols.split(",") if s.strip()]
        etf_excluded: list[str] = []
    else:
        eligible, etf_excluded = await get_eligible_symbols(market)
    provider_code = ai_config.get_batch_provider()
    model = ai_config.get_batch_model()

    # 今天已經有「這個 provider+model 組合」成功報告的標的，批次會直接回讀、不會再花錢
    # （guard.py 的既有快取判斷，見 resolve_report_slot() 閘門 3），估算時必須排除，
    # 否則會高估費用。
    today_reports = await AIReportRepository(db).list_latest_for_symbols(eligible, market, date.today())
    already_covered = [
        s for s in eligible
        if today_reports.get(s)
        and today_reports[s].get("provider") == provider_code
        and today_reports[s].get("model") == model
    ]
    fresh_candidates = [s for s in eligible if s not in already_covered]

    quota = ai_config.get_batch_daily_quota()
    today_batch_count = await AIReportRepository(db).count_succeeded_today(trigger_type="batch")
    quota_remaining = max(quota - today_batch_count, 0)
    will_call_count = min(len(fresh_candidates), quota_remaining)
    will_skip_quota_count = max(len(fresh_candidates) - quota_remaining, 0)

    avg = await AIExecutionRepository(db).get_avg_cost_for_model(provider_code, model)
    if avg:
        cost_basis = "historical"
        avg_input, avg_output = avg["avg_input_tokens"], avg["avg_output_tokens"]
        avg_cost = avg["avg_cost_usd"]
    else:
        cost_basis = "static_estimate"
        avg_input, avg_output = _FALLBACK_AVG_INPUT_TOKENS, _FALLBACK_AVG_OUTPUT_TOKENS
        avg_cost = estimate_cost(model, int(avg_input), int(avg_output))

    estimated_input_tokens = round(avg_input * will_call_count)
    estimated_output_tokens = round(avg_output * will_call_count)
    estimated_cost_usd = round(avg_cost * will_call_count, 4) if avg_cost is not None else None

    return {
        "success": True,
        "data": {
            "market": market,
            "provider": provider_code,
            "model": model,
            "eligible_count": len(eligible),
            "etf_excluded_count": len(etf_excluded),
            "already_covered_count": len(already_covered),
            "will_call_count": will_call_count,
            "will_skip_quota_count": will_skip_quota_count,
            "quota_daily": quota,
            "quota_remaining": quota_remaining,
            "estimated_input_tokens": estimated_input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "estimated_total_tokens": estimated_input_tokens + estimated_output_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "cost_basis": cost_basis,
        },
    }


class TriggerBatchRequest(BaseModel):
    market: str = "tw"
    # 戰情室多選標的手動觸發時帶入；未帶（None）則維持既有「整份監控清單」行為。
    symbols: Optional[list[str]] = None


@router.post("/trigger", summary="立即執行一次監控清單批次，或（帶 symbols 時）僅對戰情室多選的標的子集合執行（同步執行，回傳結果彙總；前端應先呼叫 /estimate 並取得使用者確認）")
async def trigger_batch(req: TriggerBatchRequest):
    if not ai_config.is_enabled():
        raise AIDisabledException("AI 技術分析報告功能未啟用（AI_ANALYSIS_ENABLED=false）")
    if not ai_config.get_batch_enabled():
        raise AIDisabledException("批次功能未啟用，請先在戰情室「批次設定」開啟（AI_BATCH_ENABLED=false）")

    from ai.batch_job import run_watchlist_batch
    result = await run_watchlist_batch(req.market, symbols=req.symbols)
    return {"success": True, "data": result}
