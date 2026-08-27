"""
ai/guard.py
六道成本與併發閘門（見 docs/16.AI技術分析/AI技術分析規劃.md §4.6）：
0 功能旗標 → 1 授權（端點層 Depends(require_owner)，不在此檔）→ 2 儲存可用性（DB 連線）→
3 當日既有報告 → 4 每日總量 → 5 佔位取得執行權（ADR-AI-16）。

本模組只負責「能不能呼叫 LLM」的裁決；實際呼叫與紀錄寫入在 ai_analysis.py 端點與
ai/recorder.py。閘門 5 的 SQL 細節見 repositories/ai_report_repository.py。
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from ai import config as ai_config
from ai.errors import AIDisabledException, AIQuotaExceededException, AIAnalysisInProgressException
from repositories.ai_report_repository import AIReportRepository
from repositories.ai_execution_repository import AIExecutionRepository

logger = logging.getLogger("mystock-backend")


@dataclass
class GuardDecision:
    outcome: Literal["cached", "acquired"]
    report: dict | None = None       # outcome == "cached"
    report_id: int | None = None     # outcome == "acquired"
    attempt_no: int = 1
    forced: bool = False


def check_enabled() -> None:
    """閘門 0。未啟用時完全不得碰資料庫或外部 API（ADR-AI-05、AC-AI-01）。"""
    if not ai_config.is_enabled():
        raise AIDisabledException("AI 技術分析報告功能未啟用")


async def resolve_report_slot(
    session: AsyncSession, *, symbol: str, market: str, trade_date: date, provider: str, model: str,
    stock_name: str | None, chart_period: str, chart_months: int,
    chart_start_date: str | None, chart_end_date: str | None,
    force: bool = False,
) -> GuardDecision:
    """閘門 2～5。呼叫前必須先通過 check_enabled() 與端點層的 require_owner。

    v3.4／ADR-AI-21：唯一鍵含 provider+model——同一標的同一交易日的「一次」，
    是針對每個 (provider, model) 組合各自算一次，換模型即可再產生一份獨立報告。

    - 已有 succeeded 報告（同一 provider+model）→ outcome="cached"（不計費，AC-AI-04）
    - 取得執行權（新列或接手失敗/孤兒列）→ outcome="acquired"，呼叫端接著打 LLM
    - 都拿不到且非孤兒 → 409 AI_ANALYSIS_IN_PROGRESS（AC-AI-06 的併發防線）
    """
    report_repo = AIReportRepository(session)
    exec_repo = AIExecutionRepository(session)

    # 開發除錯逃生門：force 只在設定允許時才生效，否則視同一般請求（§4.6）。
    # 必須先算出這個「實際生效」的 forced，後面所有閘門一律只看 forced、不得看原始
    # request 帶來的 force——否則使用者傳 force=true 但設定不允許時，仍會被誤判為
    # 該跳過閘門 3／4，甚至在閘門 5 兩步都拿不到執行權時錯把「已有成功報告」誤判成
    # 409 進行中，而不是正確地回讀既有報告。
    forced = force and ai_config.allow_force_regenerate()

    # 閘門 3：當日（同一 provider+model）已有成功報告
    existing = await report_repo.get_succeeded_report(symbol, market, trade_date, provider, model)
    if existing and not forced:
        return GuardDecision(outcome="cached", report=existing)

    # 閘門 4：全站每日新報告總量，跨所有 provider／model 合併計算（回讀既有報告不受此限制，AC-AI-10）
    if not forced:
        today_count = await report_repo.count_succeeded_today()
        if today_count >= ai_config.get_daily_quota():
            raise AIQuotaExceededException(f"今日新報告數已達上限（{ai_config.get_daily_quota()}）")

    # 閘門 5：佔位取得執行權（ADR-AI-16）
    if forced:
        slot_id = await report_repo.force_reacquire(symbol, market, trade_date, provider, model)
        if slot_id is None:
            slot_id = await report_repo.try_acquire_slot(
                symbol, market, trade_date, provider, model, stock_name,
                chart_period, chart_months, chart_start_date, chart_end_date,
            )
    else:
        slot_id = await report_repo.try_acquire_slot(
            symbol, market, trade_date, provider, model, stock_name,
            chart_period, chart_months, chart_start_date, chart_end_date,
        )

    if slot_id is None:
        slot_id = await report_repo.try_reclaim_slot(
            symbol, market, trade_date, provider, model, ai_config.get_stuck_timeout_min()
        )

    if slot_id is None:
        # 兩步都拿不到執行權：可能是他人剛完成（回讀），或他人正在執行中且未逾時（409）
        current = await report_repo.get_by_key(symbol, market, trade_date, provider, model)
        if current and current["status"] == "succeeded" and not forced:
            return GuardDecision(outcome="cached", report=current)
        raise AIAnalysisInProgressException(f"{market}/{symbol}（{provider}/{model}）的 AI 分析正在進行中，請稍後再試")

    attempt_no = await exec_repo.count_by_report(slot_id) + 1
    return GuardDecision(outcome="acquired", report_id=slot_id, attempt_no=attempt_no, forced=forced)
