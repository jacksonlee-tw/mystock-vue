"""
repositories/ai_report_repository.py
`ai_analysis_report` 的唯一 SQL 入口（見 docs/16.AI技術分析/AI技術分析規劃.md §5）。
所有對此表的讀寫都必須經由此 Repository，`ai/` 套件內不得直接操作 SQLAlchemy session
（比照 notify 平台鐵則 R3，見 repositories/notify_repository.py）。
"""
from __future__ import annotations
import json
import logging
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("mystock-backend")


class AIReportRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    # ── 併發佔位取得執行權（ADR-AI-16／ADR-AI-21，§5.8）─────────────
    # v3.4 起唯一鍵含 provider／model（見 V15 遷移）：換模型視為另一份獨立報告，
    # 同一個 (provider, model) 組合同一交易日仍然只有一份。
    async def try_acquire_slot(
        self, symbol: str, market: str, trade_date: date, provider: str, model: str,
        stock_name: str | None, chart_period: str, chart_months: int,
        chart_start_date: str | None, chart_end_date: str | None,
        trigger_type: str = "manual",
    ) -> int | None:
        """步驟 1：嘗試以新列佔位。成功回傳新列 id，該標的當日同一 provider+model 已有紀錄則回傳 None。

        trigger_type（Phase5-三層式 AI 決策引擎與戰情室.md §8／FR-5.3）：'manual'（預設，個股頁
        手動點擊）或 'batch'（監控清單排程批次），供 count_succeeded_today() 拆分配額計算。"""
        result = await self._s.execute(
            text("""
                INSERT INTO ai_analysis_report
                       (symbol, market_type, trade_date, provider, model, status, stock_name,
                        chart_period, chart_months, chart_start_date, chart_end_date, trigger_type)
                VALUES (:symbol, :market, :trade_date, :provider, :model, 'running', :name,
                        :period, :months, :start_date, :end_date, :trigger_type)
                ON CONFLICT (market_type, symbol, trade_date, provider, model) DO NOTHING
                RETURNING id
            """),
            {
                "symbol": symbol, "market": market, "trade_date": trade_date,
                "provider": provider, "model": model, "name": stock_name,
                "period": chart_period, "months": chart_months,
                "start_date": chart_start_date, "end_date": chart_end_date,
                "trigger_type": trigger_type,
            }
        )
        await self._s.flush()
        return result.scalar()

    async def try_reclaim_slot(
        self, symbol: str, market: str, trade_date: date, provider: str, model: str, stuck_min: int,
        trigger_type: str = "manual",
    ) -> int | None:
        """步驟 2：接手同一 provider+model 組合失敗過的列或逾時的孤兒 running 列。

        trigger_type 必須一起改寫（Phase5 §8／AC-P5-09）：接手的那一列可能是另一種來源留下的
        （例如上午手動點擊失敗、下午批次接手重跑），若沿用舊值，這次成功會被算進錯誤的配額桶，
        兩份配額就不再互不排擠。這一列的最終歸屬是「實際把它跑成功的那一次呼叫」的來源。"""
        result = await self._s.execute(
            text("""
                UPDATE ai_analysis_report
                   SET status       = 'running',
                       error_code   = NULL,
                       trigger_type = :trigger_type,
                       updated_at   = CURRENT_TIMESTAMP
                 WHERE market_type = :market
                   AND symbol      = :symbol
                   AND trade_date  = :trade_date
                   AND provider    = :provider
                   AND model       = :model
                   AND (
                         status = 'failed'
                         OR (status = 'running'
                             AND updated_at < CURRENT_TIMESTAMP - make_interval(mins => :stuck_min))
                       )
                RETURNING id
            """),
            {
                "market": market, "symbol": symbol, "trade_date": trade_date,
                "provider": provider, "model": model, "stuck_min": stuck_min,
                "trigger_type": trigger_type,
            }
        )
        await self._s.flush()
        return result.scalar()

    async def force_reacquire(
        self, symbol: str, market: str, trade_date: date, provider: str, model: str,
        trigger_type: str = "manual",
    ) -> int | None:
        """開發除錯用逃生門（AI_ALLOW_FORCE_REGENERATE，§4.6）：無視現有 status 強制取得執行權。
        僅供開發環境使用；呼叫端必須把對應的 ai_llm_execution 標記 is_dry_run=True。"""
        result = await self._s.execute(
            text("""
                UPDATE ai_analysis_report
                   SET status = 'running', error_code = NULL, updated_at = CURRENT_TIMESTAMP,
                       trigger_type = :trigger_type
                 WHERE market_type = :market AND symbol = :symbol AND trade_date = :trade_date
                   AND provider = :provider AND model = :model
                RETURNING id
            """),
            {
                "market": market, "symbol": symbol, "trade_date": trade_date,
                "provider": provider, "model": model, "trigger_type": trigger_type,
            }
        )
        await self._s.flush()
        return result.scalar()

    # ── 查詢 ─────────────────────────────────────────────────────
    async def get_succeeded_report(
        self, symbol: str, market: str, trade_date: date, provider: str, model: str,
    ) -> dict | None:
        result = await self._s.execute(
            text("""
                SELECT * FROM ai_analysis_report
                 WHERE market_type = :market AND symbol = :symbol AND trade_date = :trade_date
                   AND provider = :provider AND model = :model AND status = 'succeeded'
                 LIMIT 1
            """),
            {"market": market, "symbol": symbol, "trade_date": trade_date, "provider": provider, "model": model}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def get_by_key(
        self, symbol: str, market: str, trade_date: date, provider: str, model: str,
    ) -> dict | None:
        """不篩 status，供閘門判斷目前狀態（running／failed／succeeded）用。"""
        result = await self._s.execute(
            text("""
                SELECT * FROM ai_analysis_report
                 WHERE market_type = :market AND symbol = :symbol AND trade_date = :trade_date
                   AND provider = :provider AND model = :model
                 LIMIT 1
            """),
            {"market": market, "symbol": symbol, "trade_date": trade_date, "provider": provider, "model": model}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def list_latest_for_symbols(
        self, symbols: list[str], market: str, since_date: date,
    ) -> dict[str, dict]:
        """戰情室批次查詢（Phase5 FR-5.5 AC-P5-17）：一次查完所有監控標的的最新成功報告，
        避免前端對每檔標的各發一次請求。同一標的同一交易日可能有多個 provider/model 的報告，
        取 trade_date 最新、同日再取 generated_at 最新那筆代表該標的最新結果。
        回傳 {symbol: row}，查無報告的標的不在字典內。

        since_date 是「往回看到哪一天為止」的下界，不是等值比對——報告的 trade_date 是行情的
        最新交易日，不是 date.today()：週末與連假沒有新交易日，美股批次在台灣時間清晨跑完時
        對應的也是前一個美股交易日。若寫成 trade_date = CURRENT_DATE，戰情室會在這些情境下
        整頁顯示「尚未產生」，而實際上報告就在資料庫裡（AC-P5-14）。"""
        if not symbols:
            return {}
        result = await self._s.execute(
            text("""
                SELECT DISTINCT ON (symbol) *
                  FROM ai_analysis_report
                 WHERE market_type = :market AND trade_date >= :since_date
                   AND status = 'succeeded' AND symbol = ANY(:symbols)
                 ORDER BY symbol, trade_date DESC, generated_at DESC
            """),
            {"market": market, "since_date": since_date, "symbols": symbols}
        )
        return {row["symbol"]: dict(row) for row in result.mappings()}

    async def get_previous_verdict(
        self, symbol: str, market: str, provider: str, model: str, before_date: date,
    ) -> str | None:
        """FR-5.4 推播摘要：取同一標的、同一 provider+model 在 before_date 之前最近一筆成功報告的
        verdict，供批次比對「今日 verdict 是否翻多／翻空」。查無歷史報告視為無從比較，回傳 None。"""
        result = await self._s.execute(
            text("""
                SELECT verdict FROM ai_analysis_report
                 WHERE market_type = :market AND symbol = :symbol
                   AND provider = :provider AND model = :model
                   AND status = 'succeeded' AND trade_date < :before_date
                 ORDER BY trade_date DESC, generated_at DESC
                 LIMIT 1
            """),
            {
                "market": market, "symbol": symbol, "provider": provider,
                "model": model, "before_date": before_date,
            }
        )
        return result.scalar()

    async def get_by_id(self, report_id: int) -> dict | None:
        result = await self._s.execute(
            text("SELECT * FROM ai_analysis_report WHERE id = :id"),
            {"id": report_id}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def list_reports(
        self, market: str | None = None, symbol: str | None = None,
        provider: str | None = None, model: str | None = None,
        date_from: date | None = None, date_to: date | None = None,
        verdict: str | None = None, status: str | None = "succeeded",
        limit: int = 20, offset: int = 0,
    ) -> tuple[list[dict], int]:
        """歷史報告列表（分頁）。status=None 代表不篩（含 running/failed），
        status='succeeded'（預設）只回成功報告，呼叫端可傳 'all' 代表不篩。
        provider／model 用於 /reports/latest 精確判斷「這個模型組合今天是否已有報告」（§7.3）。"""
        conditions = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if status and status != "all":
            conditions.append("status = :status")
            params["status"] = status
        if market:
            conditions.append("market_type = :market")
            params["market"] = market
        if symbol:
            conditions.append("symbol = :symbol")
            params["symbol"] = symbol
        if provider:
            conditions.append("provider = :provider")
            params["provider"] = provider
        if model:
            conditions.append("model = :model")
            params["model"] = model
        if date_from:
            conditions.append("trade_date >= :date_from")
            params["date_from"] = date_from
        if date_to:
            conditions.append("trade_date <= :date_to")
            params["date_to"] = date_to
        if verdict:
            conditions.append("verdict = :verdict")
            params["verdict"] = verdict

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # 列表不含 report_markdown / quant_summary（體積大，§6.2）
        result = await self._s.execute(
            text(f"""
                SELECT id, symbol, market_type, trade_date, status, stock_name, provider, model,
                       chart_period, chart_months, chart_start_date, chart_end_date,
                       verdict, headline, support_levels, resistance_levels, stop_loss,
                       target_price, rule_signal_alignment, trigger_type,
                       confidence, truncated, error_code, generated_at, updated_at
                  FROM ai_analysis_report
                  {where_clause}
                 ORDER BY generated_at DESC
                 LIMIT :limit OFFSET :offset
            """),
            params
        )
        rows = [dict(r) for r in result.mappings()]

        count_result = await self._s.execute(
            text(f"SELECT COUNT(*) FROM ai_analysis_report {where_clause}"),
            {k: v for k, v in params.items() if k not in ("limit", "offset")}
        )
        total = count_result.scalar() or 0
        return rows, total

    async def count_succeeded_today(self, trigger_type: str | None = None) -> int:
        """今日（依 generated_at 的本機日期）成功產生的新報告數，供 §4.6 閘門 4 使用。

        trigger_type（Phase5 §8）：帶入時只算該來源（'manual'／'batch'），供拆分後的配額各自
        計算；不帶則沿用原行為，跨來源合併計算（GET /api/v1/ai/status 的全站總量仍用這個模式）。"""
        if trigger_type:
            result = await self._s.execute(
                text("""
                    SELECT COUNT(*) FROM ai_analysis_report
                     WHERE status = 'succeeded' AND generated_at::date = CURRENT_DATE
                       AND trigger_type = :trigger_type
                """),
                {"trigger_type": trigger_type}
            )
        else:
            result = await self._s.execute(
                text("""
                    SELECT COUNT(*) FROM ai_analysis_report
                     WHERE status = 'succeeded' AND generated_at::date = CURRENT_DATE
                """)
            )
        return result.scalar() or 0

    # ── 寫入 ─────────────────────────────────────────────────────
    async def mark_succeeded(self, report_id: int, data: dict) -> None:
        """model 不在 SET 之列：v3.4 起 model 是唯一鍵的一部分，於 try_acquire_slot() 佔位時
        就已固定，不會、也不應該在完成時被改寫（見 ADR-AI-21）。"""
        await self._s.execute(
            text("""
                UPDATE ai_analysis_report
                   SET status                 = 'succeeded',
                       verdict                = :verdict,
                       headline               = :headline,
                       support_levels         = :support_levels,
                       resistance_levels      = :resistance_levels,
                       stop_loss              = :stop_loss,
                       target_price           = :target_price,
                       rule_signal_alignment  = :rule_signal_alignment,
                       report_markdown        = :report_markdown,
                       confidence             = :confidence,
                       quant_summary          = :quant_summary,
                       truncated              = :truncated,
                       error_code             = NULL,
                       updated_at             = CURRENT_TIMESTAMP
                 WHERE id = :id
            """),
            {
                "id": report_id,
                "verdict": data["verdict"],
                "headline": data["headline"],
                "support_levels": json.dumps(data["support_levels"]),
                "resistance_levels": json.dumps(data["resistance_levels"]),
                "stop_loss": data.get("stop_loss"),
                "target_price": data.get("target_price"),
                "rule_signal_alignment": data.get("rule_signal_alignment"),
                "report_markdown": data["report_markdown"],
                "confidence": data["confidence"],
                "quant_summary": json.dumps(data["quant_summary"]),
                "truncated": data.get("truncated", False),
            }
        )

    async def mark_failed(self, report_id: int, error_code: str) -> None:
        await self._s.execute(
            text("""
                UPDATE ai_analysis_report
                   SET status = 'failed', error_code = :error_code, updated_at = CURRENT_TIMESTAMP
                 WHERE id = :id
            """),
            {"id": report_id, "error_code": error_code}
        )

    async def delete_report(self, report_id: int) -> bool:
        result = await self._s.execute(
            text("DELETE FROM ai_analysis_report WHERE id = :id"),
            {"id": report_id}
        )
        return result.rowcount > 0

    # ── 孤兒回收（比照 repositories/market_repository.py 的
    #    reap_orphaned_fetch_jobs()，main.py lifespan 啟動時呼叫，§5.8）──
    async def reap_orphaned(self, stuck_min: int) -> int:
        result = await self._s.execute(
            text("""
                UPDATE ai_analysis_report
                   SET status = 'failed', error_code = 'AI_ORPHANED_ON_STARTUP', updated_at = CURRENT_TIMESTAMP
                 WHERE status = 'running'
                   AND updated_at < CURRENT_TIMESTAMP - make_interval(mins => :stuck_min)
            """),
            {"stuck_min": stuck_min}
        )
        return result.rowcount or 0

    # ── 資料保留（§5.10）───────────────────────────────────────────
    async def purge_expired(self, retention_days: int) -> int:
        result = await self._s.execute(
            text("""
                DELETE FROM ai_analysis_report
                 WHERE generated_at < CURRENT_TIMESTAMP - make_interval(days => :days)
            """),
            {"days": retention_days}
        )
        return result.rowcount or 0
