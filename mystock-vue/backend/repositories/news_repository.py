"""
repositories/news_repository.py
`stock_news` / `stock_discussion_buzz` / `macro_indicators` 的唯一 SQL 入口（見
docs/16.AI技術分析/Phase4-輕量化新聞輿情與總經監控.md §7、CLAUDE.md「SQL 邊界」規範）。

比照 repositories/industry_chain_repository.py：建構子注入 AsyncSession、用 text() 寫原生
SQL（不用 ORM model），呼叫端自行決定何時 commit——本類別本身不 commit。

L1/L2 去重（唯一索引）在 INSERT 階段由資料庫本身把關；L3（SimHash 近似比對）無法表達成
唯一索引，屬於應用邏輯，見 services/news_dedup.py 呼叫 find_recent_candidates_for_dedup()
取回候選後自行比對、再呼叫 mark_duplicate()。
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from db.session import _database_url

logger = logging.getLogger("mystock-backend")

# ── 給同步爬蟲模組（services/news_fetcher.py）使用的橋接：獨立背景連線池 ──────
# 比照 repositories/stock_repository.py／market_repository.py 各自維護一份不跟主 FastAPI
# event loop 共用的 engine，避免 run_async() 結束時的 dispose 波及主 loop 正在服務的請求。
_bg_engine: AsyncEngine | None = None
_bg_session_factory: async_sessionmaker | None = None


def _get_bg_session_factory() -> async_sessionmaker:
    global _bg_engine, _bg_session_factory
    if _bg_session_factory is None:
        _bg_engine = create_async_engine(_database_url(), pool_pre_ping=True)
        _bg_session_factory = async_sessionmaker(_bg_engine, expire_on_commit=False)
    return _bg_session_factory


async def _dispose_bg_engine() -> None:
    global _bg_engine, _bg_session_factory
    if _bg_engine is not None:
        await _bg_engine.dispose()
    _bg_engine = None
    _bg_session_factory = None


@asynccontextmanager
async def get_background_session():
    """給 news_fetcher.py 在 `run_async()` 包裹的協程內取用的 session context manager。"""
    session: AsyncSession = _get_bg_session_factory()()
    try:
        yield session
    finally:
        await session.close()


def run_async(coro):
    """讓同步的 services/news_fetcher.py 可以呼叫 async 版的 NewsRepository 方法，
    結束時 dispose 掉的是上面 _bg_engine（背景專用），不影響主 loop 的全域連線池。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("run_async() 不可在既有的事件迴圈中呼叫，請直接 await 對應的 async 方法")

    async def _runner():
        try:
            return await coro
        finally:
            await _dispose_bg_engine()

    return asyncio.run(_runner())


def _row_to_dict(row) -> dict:
    d = dict(row._mapping)
    if d.get("extra_meta") and isinstance(d["extra_meta"], str):
        d["extra_meta"] = json.loads(d["extra_meta"])
    return d


class NewsRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    # ── stock_news ──────────────────────────────────────────────────
    async def insert_news_if_new(self, row: dict) -> Optional[int]:
        """插入一則新聞；違反 L1 `(symbol, news_url)` 或 L2
        `(symbol, title_hash, effective_trade_date)` 任一唯一鍵即視為重複，回傳 None。

        `ON CONFLICT (symbol, news_url) DO NOTHING` 只吸收 L1 這個特定唯一鍵的衝突；
        若撞的是 L2（不同來源、不同網址，但同一標的同一交易日的正規化標題相同），INSERT
        仍會照常拋出例外——用 SAVEPOINT（begin_nested）局部吸收，不拖垮外層交易，讓呼叫端
        可以在同一個 session 裡繼續處理下一則新聞。"""
        try:
            async with self._s.begin_nested():
                result = await self._s.execute(
                    text("""
                        INSERT INTO stock_news
                               (symbol, market_type, source, title, news_url, published_at,
                                effective_trade_date, title_hash, simhash, extra_meta)
                        VALUES (:symbol, :market_type, :source, :title, :news_url, :published_at,
                                :effective_trade_date, :title_hash, :simhash, :extra_meta)
                        ON CONFLICT (symbol, news_url) DO NOTHING
                        RETURNING id
                    """),
                    {**row, "extra_meta": json.dumps(row.get("extra_meta") or {}, ensure_ascii=False)},
                )
                inserted = result.first()
                return inserted[0] if inserted else None
        except IntegrityError:
            return None

    async def find_recent_candidates_for_dedup(
        self, *, symbol: str, since: datetime, exclude_id: Optional[int] = None
    ) -> list[dict]:
        """L3 SimHash 比對的候選集合：同一標的、`dedup_window_hours` 回溯範圍內、
        目前仍是代表列（`is_duplicate = false`）的既有新聞。"""
        stmt = text("""
            SELECT id, source, simhash, effective_trade_date
              FROM stock_news
             WHERE symbol = :symbol
               AND is_duplicate = FALSE
               AND published_at >= :since
               AND simhash IS NOT NULL
               AND (:exclude_id IS NULL OR id != :exclude_id)
             ORDER BY published_at DESC
        """)
        result = await self._s.execute(stmt, {"symbol": symbol, "since": since, "exclude_id": exclude_id})
        return [_row_to_dict(r) for r in result.fetchall()]

    async def mark_duplicate(self, news_id: int, duplicate_of_id: int) -> None:
        await self._s.execute(
            text("UPDATE stock_news SET is_duplicate = TRUE, duplicate_of_id = :dup WHERE id = :id"),
            {"id": news_id, "dup": duplicate_of_id},
        )

    async def list_by_symbol(
        self, *, symbol: str, market_type: str, include_duplicates: bool = False,
        page: int = 1, page_size: int = 20,
    ) -> tuple[list[dict], int]:
        where_dup = "" if include_duplicates else "AND is_duplicate = FALSE"
        count_stmt = text(f"""
            SELECT COUNT(*) FROM stock_news
             WHERE symbol = :symbol AND market_type = :market_type {where_dup}
        """)
        total = (await self._s.execute(count_stmt, {"symbol": symbol, "market_type": market_type})).scalar_one()

        rows_stmt = text(f"""
            SELECT id, symbol, market_type, source, title, news_url, published_at,
                   effective_trade_date, is_duplicate, sentiment_score, sentiment_label,
                   sentiment_engine, extra_meta
              FROM stock_news
             WHERE symbol = :symbol AND market_type = :market_type {where_dup}
             ORDER BY effective_trade_date DESC, published_at DESC
             LIMIT :limit OFFSET :offset
        """)
        result = await self._s.execute(rows_stmt, {
            "symbol": symbol, "market_type": market_type,
            "limit": page_size, "offset": (page - 1) * page_size,
        })
        return [_row_to_dict(r) for r in result.fetchall()], total

    async def purge_expired(self, *, retention_months: int) -> int:
        """§13 資料保留：逾 `retention_months` 個月的新聞列刪除，逐日彙總值另存不受影響
        （彙總落在別的資料結構，不在本表）。"""
        stmt = text("""
            DELETE FROM stock_news
             WHERE effective_trade_date < (CURRENT_DATE - (:months || ' months')::interval)
        """)
        result = await self._s.execute(stmt, {"months": retention_months})
        return result.rowcount or 0

    # ── stock_discussion_buzz ───────────────────────────────────────
    async def upsert_buzz(self, *, symbol: str, market_type: str, trade_date: date,
                           source: str, post_count: int, percentile_rank: Optional[float]) -> None:
        await self._s.execute(
            text("""
                INSERT INTO stock_discussion_buzz
                       (symbol, market_type, trade_date, source, post_count, percentile_rank)
                VALUES (:symbol, :market_type, :trade_date, :source, :post_count, :percentile_rank)
                ON CONFLICT (source, symbol, trade_date) DO UPDATE
                   SET post_count = EXCLUDED.post_count,
                       percentile_rank = EXCLUDED.percentile_rank
            """),
            {
                "symbol": symbol, "market_type": market_type, "trade_date": trade_date,
                "source": source, "post_count": post_count, "percentile_rank": percentile_rank,
            },
        )

    async def get_buzz_history(self, *, symbol: str, source: str, window: int) -> list[dict]:
        """近 `window` 個交易日的討論則數，供 §4.4 分位數計算使用（呼叫端自行套用
        indicators/chip.py 的 rolling_percentile()，本方法只負責取資料，不算分位數）。"""
        stmt = text("""
            SELECT trade_date, post_count FROM stock_discussion_buzz
             WHERE symbol = :symbol AND source = :source
             ORDER BY trade_date DESC LIMIT :window
        """)
        result = await self._s.execute(stmt, {"symbol": symbol, "source": source, "window": window})
        return [_row_to_dict(r) for r in result.fetchall()]

    # ── macro_indicators ────────────────────────────────────────────
    async def upsert_macro_indicator(self, *, indicator_code: str, indicator_date: date,
                                      release_date: date, value: float, source: str = "FRED") -> None:
        await self._s.execute(
            text("""
                INSERT INTO macro_indicators
                       (indicator_code, indicator_date, release_date, value, source)
                VALUES (:indicator_code, :indicator_date, :release_date, :value, :source)
                ON CONFLICT (indicator_code, indicator_date) DO UPDATE
                   SET release_date = EXCLUDED.release_date,
                       value = EXCLUDED.value,
                       fetched_at = CURRENT_TIMESTAMP
            """),
            {
                "indicator_code": indicator_code, "indicator_date": indicator_date,
                "release_date": release_date, "value": value, "source": source,
            },
        )

    async def get_latest_visible_indicator(self, *, indicator_code: str, as_of: date) -> Optional[dict]:
        """`macro_filter` 的唯一時間依據：只讀 `release_date <= as_of` 的紀錄（ADR-P4-05,
        比照月營收 look-ahead bias 防線，見 §5.1）。"""
        stmt = text("""
            SELECT indicator_code, indicator_date, release_date, value
              FROM macro_indicators
             WHERE indicator_code = :code AND release_date <= :as_of
             ORDER BY release_date DESC LIMIT 1
        """)
        result = await self._s.execute(stmt, {"code": indicator_code, "as_of": as_of})
        row = result.first()
        return _row_to_dict(row) if row else None
