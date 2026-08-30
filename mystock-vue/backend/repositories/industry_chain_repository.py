"""
repositories/industry_chain_repository.py
`industry_chain_edges` / `industry_chain_lead_lag_cache` 的唯一 SQL 入口（見
docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §5、CLAUDE.md「SQL 邊界」規範）。

比照 repositories/activity_log_repository.py：建構子注入 AsyncSession、用 text() 寫原生
SQL（不用 ORM model），呼叫端（未來的 industry_chain/extractor.py、API 端點）自行決定何時
commit——本類別本身不 commit，一律留給呼叫端統一交易邊界（比照既有 repositories 慣例）。

本批次（第一批交付）只有邊與快取的基本 CRUD；BFS／篩選查詢留待 graph.py／spillover.py
接上時再擴充，避免預先猜測尚未定案的查詢形狀。

補充（FR-10 格蘭傑因果檢定）：`update_granger_result()` 是本檔案唯一為 Granger 新增的方法，
見該方法 docstring 說明為何用 `UPDATE` 而非既有 `upsert_lead_lag_cache()` 的 `ON CONFLICT` 模式。
"""
from __future__ import annotations
import json
import logging
from datetime import date
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("mystock-backend")


def _row_to_dict(row) -> dict:
    d = dict(row._mapping)
    if d.get("extra_data") and isinstance(d["extra_data"], str):
        d["extra_data"] = json.loads(d["extra_data"])
    return d


class IndustryChainRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    # ── industry_chain_edges ────────────────────────────────────
    async def upsert_edge(
        self, *, chain_id: str, upstream_symbol: str, downstream_symbol: str,
        upstream_market: str, downstream_market: str, relation_tier: int,
        component_type: Optional[str] = None, source: str, is_verified: bool = False,
        first_seen_date: Optional[date] = None, last_confirmed_date: Optional[date] = None,
        extra_data: Optional[dict] = None,
    ) -> int:
        """`(chain_id, upstream_symbol, downstream_symbol)` 已存在則更新非鍵欄位（含
        `last_confirmed_date`／`extra_data`），不動 `is_active`——軟刪除只能由呼叫端另外
        明確操作，不隨每次 upsert 被動改動（ADR-IC-15：只增不自動刪）。`is_verified` 同樣
        不因重複 upsert 而被覆寫回 FALSE：已核可的邊即使之後又被同一來源重新提交，仍維持
        已核可狀態（見 AC-IC-22 的 upsert 語意）。"""
        result = await self._s.execute(
            text("""
                INSERT INTO industry_chain_edges
                       (chain_id, upstream_symbol, downstream_symbol,
                        upstream_market, downstream_market, relation_tier,
                        component_type, source, is_verified,
                        first_seen_date, last_confirmed_date, extra_data)
                VALUES (:chain_id, :upstream_symbol, :downstream_symbol,
                        :upstream_market, :downstream_market, :relation_tier,
                        :component_type, :source, :is_verified,
                        :first_seen_date, :last_confirmed_date, :extra_data)
                ON CONFLICT (chain_id, upstream_symbol, downstream_symbol) DO UPDATE
                   SET component_type      = EXCLUDED.component_type,
                       last_confirmed_date = COALESCE(EXCLUDED.last_confirmed_date, industry_chain_edges.last_confirmed_date),
                       extra_data          = EXCLUDED.extra_data,
                       updated_at          = CURRENT_TIMESTAMP
                RETURNING id
            """),
            {
                "chain_id": chain_id, "upstream_symbol": upstream_symbol, "downstream_symbol": downstream_symbol,
                "upstream_market": upstream_market, "downstream_market": downstream_market,
                "relation_tier": relation_tier, "component_type": component_type,
                "source": source, "is_verified": is_verified,
                "first_seen_date": first_seen_date, "last_confirmed_date": last_confirmed_date,
                "extra_data": json.dumps(extra_data) if extra_data is not None else None,
            }
        )
        return result.scalar()

    async def get_edge(self, chain_id: str, upstream_symbol: str, downstream_symbol: str) -> Optional[dict]:
        result = await self._s.execute(
            text("""
                SELECT * FROM industry_chain_edges
                 WHERE chain_id = :chain_id AND upstream_symbol = :up AND downstream_symbol = :down
            """),
            {"chain_id": chain_id, "up": upstream_symbol, "down": downstream_symbol}
        )
        row = result.first()
        return _row_to_dict(row) if row else None

    async def list_edges(
        self, *, chain_id: Optional[str] = None, is_verified: Optional[bool] = None,
        is_active: Optional[bool] = True,
    ) -> list[dict]:
        conditions: list[str] = []
        params: dict[str, Any] = {}
        if chain_id is not None:
            conditions.append("chain_id = :chain_id")
            params["chain_id"] = chain_id
        if is_verified is not None:
            conditions.append("is_verified = :is_verified")
            params["is_verified"] = is_verified
        if is_active is not None:
            conditions.append("is_active = :is_active")
            params["is_active"] = is_active
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        result = await self._s.execute(
            text(f"""
                SELECT * FROM industry_chain_edges
                {where_clause}
                ORDER BY chain_id, relation_tier, downstream_symbol, upstream_symbol
            """),
            params
        )
        return [_row_to_dict(row) for row in result.fetchall()]

    # ── industry_chain_lead_lag_cache ───────────────────────────
    async def upsert_lead_lag_cache(
        self, *, edge_id: int, window_start: date, window_end: date,
        peak_lag_days: Optional[int], correlation_coefficient: Optional[float], sample_size: int,
    ) -> int:
        """同一條邊、同一個計算截止日只保留一筆，重算時覆蓋（FR-8）。"""
        result = await self._s.execute(
            text("""
                INSERT INTO industry_chain_lead_lag_cache
                       (edge_id, window_start, window_end, peak_lag_days, correlation_coefficient, sample_size)
                VALUES (:edge_id, :window_start, :window_end, :peak_lag_days, :correlation_coefficient, :sample_size)
                ON CONFLICT (edge_id, window_end) DO UPDATE
                   SET window_start            = EXCLUDED.window_start,
                       peak_lag_days           = EXCLUDED.peak_lag_days,
                       correlation_coefficient = EXCLUDED.correlation_coefficient,
                       sample_size             = EXCLUDED.sample_size,
                       computed_at             = CURRENT_TIMESTAMP
                RETURNING id
            """),
            {
                "edge_id": edge_id, "window_start": window_start, "window_end": window_end,
                "peak_lag_days": peak_lag_days, "correlation_coefficient": correlation_coefficient,
                "sample_size": sample_size,
            }
        )
        return result.scalar()

    async def list_lead_lag_for_edge(self, edge_id: int) -> list[dict]:
        result = await self._s.execute(
            text("""
                SELECT * FROM industry_chain_lead_lag_cache
                 WHERE edge_id = :edge_id
                 ORDER BY window_end DESC
            """),
            {"edge_id": edge_id}
        )
        return [dict(row._mapping) for row in result.fetchall()]

    # ── FR-10：格蘭傑因果檢定（V20 遷移新增欄位，ADR-IC-05 延後已解除）───
    async def update_granger_result(
        self, *, edge_id: int, window_end: date,
        granger_p_value: Optional[float], granger_p_value_adjusted: Optional[float],
        granger_significant: Optional[bool], granger_optimal_lag: Optional[int],
    ) -> int:
        """更新既有一筆 `(edge_id, window_end)` 快取列的 Granger 欄位，回傳受影響列數
        （0 或 1）。刻意用 `UPDATE` 而非 `upsert_lead_lag_cache()` 那種 `ON CONFLICT` upsert：

        `industry_chain/lead_lag_job.py` 的 `compute_granger_for_all_edges()` 一律排在
        `recompute_all_lead_lag()`（FR-19）之後執行，同一個 `window_end` 的 CCF 快取列理應
        已存在——若改用 upsert 並在 Granger 這一步重新 INSERT，會需要同時提供
        `peak_lag_days`／`correlation_coefficient`／`sample_size` 等本函式其實沒有算的欄位，
        要嘛留白覆蓋掉 CCF 剛寫入的數值（回歸），要嘛用 `COALESCE(EXCLUDED.x, 既有值)` 掩蓋
        「這欄根本沒打算被這次呼叫碰」的事實。用 `UPDATE ... WHERE edge_id AND window_end`
        語意上更誠實：找不到對應列（呼叫端未先跑過 FR-19，或該邊當月未達 CCF 樣本門檻）就
        回傳 0，呼叫端據此記警告、不硬塞一筆殘缺的快取列（見 `compute_granger_for_all_edges()`
        對 0 筆更新的處理）。"""
        result = await self._s.execute(
            text("""
                UPDATE industry_chain_lead_lag_cache
                   SET granger_p_value          = :granger_p_value,
                       granger_p_value_adjusted  = :granger_p_value_adjusted,
                       granger_significant       = :granger_significant,
                       granger_optimal_lag       = :granger_optimal_lag,
                       computed_at               = CURRENT_TIMESTAMP
                 WHERE edge_id = :edge_id AND window_end = :window_end
            """),
            {
                "edge_id": edge_id, "window_end": window_end,
                "granger_p_value": granger_p_value,
                "granger_p_value_adjusted": granger_p_value_adjusted,
                "granger_significant": granger_significant,
                "granger_optimal_lag": granger_optimal_lag,
            }
        )
        return result.rowcount or 0
