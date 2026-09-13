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
        目前仍是代表列（`is_duplicate = false`）的既有新聞。

        `CAST(:exclude_id AS BIGINT)`：asyncpg 對只出現在 `IS NULL` 分支裡的參數無法推斷型別，
        不轉型會直接拋 `AmbiguousParameterError`（實測撞過，連 `exclude_id` 帶實際整數值時也
        一樣炸，不是只有 None 的情況）。用 `CAST(... AS ...)` 而非 `:param::bigint` 簡寫語法
        ——後者在 SQLAlchemy `text()` 底下會被誤判成參數名稱的一部分，導致整個 `:exclude_id`
        沒被辨識成綁定參數（實測也撞過：`PostgresSyntaxError: syntax error at or near ":"`）。"""
        stmt = text("""
            SELECT id, source, simhash, effective_trade_date
              FROM stock_news
             WHERE symbol = :symbol
               AND is_duplicate = FALSE
               AND published_at >= :since
               AND simhash IS NOT NULL
               AND (CAST(:exclude_id AS BIGINT) IS NULL OR id != CAST(:exclude_id AS BIGINT))
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

    async def list_unscored(self, limit: int) -> list[dict]:
        """P2 情緒評分引擎的候選佇列：尚未評分（`sentiment_score IS NULL`）且非 L3 重複列。
        ADR-P4-08 後不存在 L1／L2 分流，這裡回傳的每一筆都會走 LLM 批次評分，
        不需要再篩「閘門是否成立」。"""
        stmt = text("""
            SELECT id, symbol, title FROM stock_news
             WHERE sentiment_score IS NULL AND is_duplicate = FALSE
             ORDER BY id
             LIMIT :limit
        """)
        result = await self._s.execute(stmt, {"limit": limit})
        return [_row_to_dict(r) for r in result.fetchall()]

    async def update_sentiment(self, news_id: int, *, score: float, label: str, engine: str) -> None:
        await self._s.execute(
            text("""
                UPDATE stock_news
                   SET sentiment_score = :score, sentiment_label = :label, sentiment_engine = :engine
                 WHERE id = :id
            """),
            {"id": news_id, "score": score, "label": label, "engine": engine},
        )

    async def get_recent_scores(self, *, symbol: str, market_type: str, since_date: date) -> list[dict]:
        """近 `since_date`（含）以來、已評分且非重複列的 (source, sentiment_score,
        effective_trade_date) 清單，供 §4.3 `sentiment_5d` 加權平均使用——本方法只負責取資料，
        權重由呼叫端從 `news_sources.yaml` 查表後傳入 `indicators/news_time.py` 的純函式計算，
        保持本 repository 對 YAML 設定零依賴（比照 get_buzz_history() 的既有分工）。

        `effective_trade_date` 一併回傳：`services/news_analytics.get_sentiment_5d()`（單一
        「as of 今天」數值）不需要這欄，但 P4 `ScanContext` 的逐日序列版
        （`services/chip_provider.py` 的 `sentiment_5d`）需要知道每筆分數屬於哪個交易日
        才能分桶進正確的 5 日視窗，一次查詢覆蓋整個回看範圍（`since_date` 傳整段掃描視窗的
        最早一天），不逐日各查一次。"""
        stmt = text("""
            SELECT source, sentiment_score, effective_trade_date FROM stock_news
             WHERE symbol = :symbol AND market_type = :market_type
               AND is_duplicate = FALSE AND sentiment_score IS NOT NULL
               AND effective_trade_date >= :since_date
        """)
        result = await self._s.execute(
            stmt, {"symbol": symbol, "market_type": market_type, "since_date": since_date}
        )
        return [_row_to_dict(r) for r in result.fetchall()]

    async def get_top_news(self, *, symbol: str, market_type: str, since_date: date, limit: int = 3) -> list[dict]:
        """近 `since_date`（含）以來、方向性最強（`|sentiment_score|` 最大）的前 `limit` 則
        非重複已評分新聞，供推播訊息附上「促成訊號的新聞標題與來源」（Phase4-輕量化新聞輿情與
        總經監控.md §10）——只在 `sentiment_filter` 閘門實際影響了某筆警示是否放行時才查詢
        （見 `notify/intake.py` 的呼叫端判斷），不是每筆台股警示都查一次。"""
        stmt = text("""
            SELECT title, source, news_url, sentiment_score, sentiment_label, effective_trade_date
              FROM stock_news
             WHERE symbol = :symbol AND market_type = :market_type
               AND is_duplicate = FALSE AND sentiment_score IS NOT NULL
               AND effective_trade_date >= :since_date
             ORDER BY ABS(sentiment_score) DESC, effective_trade_date DESC
             LIMIT :limit
        """)
        result = await self._s.execute(
            stmt, {"symbol": symbol, "market_type": market_type, "since_date": since_date, "limit": limit}
        )
        return [_row_to_dict(r) for r in result.fetchall()]

    async def get_news_count_by_dates(self, *, symbol: str, market_type: str, dates: list[date]) -> dict[date, int]:
        """給定一組交易日，回傳該股非重複新聞則數（缺值一律補 0）——供 §4.3 Buzz Surge
        （新聞曝光倍數）計算「近 20 交易日平均則數」使用。刻意接收明確的交易日清單而非
        `window` 天數：純用 `GROUP BY effective_trade_date` 會漏掉「當天完全沒有新聞」的
        交易日，讓平均值虛高、稀釋真正的曝光倍增訊號，所以由呼叫端先算好真正的交易日曆
        （`indicators/news_time.py` 的 `is_weekday_trading_day()`）再回頭補零。"""
        if not dates:
            return {}
        stmt = text("""
            SELECT effective_trade_date, COUNT(*) AS cnt FROM stock_news
             WHERE symbol = :symbol AND market_type = :market_type
               AND is_duplicate = FALSE
               AND effective_trade_date = ANY(:dates)
             GROUP BY effective_trade_date
        """)
        result = await self._s.execute(stmt, {"symbol": symbol, "market_type": market_type, "dates": dates})
        counts = {row.effective_trade_date: row.cnt for row in result.fetchall()}
        return {d: counts.get(d, 0) for d in dates}

    async def purge_expired(self, *, retention_months: int) -> int:
        """§13 資料保留：逾 `retention_months` 個月的新聞列刪除，逐日彙總值另存不受影響
        （彙總落在別的資料結構，不在本表）。

        用 `make_interval(months => :months)` 而非 `:months || ' months'` 字串拼接——
        asyncpg 對 `||` 運算子兩側的參數型別無法推斷（`:months` 送的是 int，`||`
        期待文字），會直接拋 `DataError: invalid input for query argument`（P7 排程
        實測撞過）；`make_interval()` 是 Postgres 內建函式，直接接受整數參數，不需要
        額外轉型。"""
        stmt = text("""
            DELETE FROM stock_news
             WHERE effective_trade_date < (CURRENT_DATE - make_interval(months => :months))
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
        indicators/news_time.py 的 percentile_rank_of()——刻意不用 indicators/chip.py 的
        rolling_percentile()，那個函式算的是相反方向的問題，見該函式 docstring 的說明；
        本方法只負責取資料，不算分位數）。"""
        stmt = text("""
            SELECT trade_date, post_count FROM stock_discussion_buzz
             WHERE symbol = :symbol AND source = :source
             ORDER BY trade_date DESC LIMIT :window
        """)
        result = await self._s.execute(stmt, {"symbol": symbol, "source": source, "window": window})
        return [_row_to_dict(r) for r in result.fetchall()]

    async def get_buzz_percentile_series(self, *, symbol: str, source: str, since_date: date) -> list[dict]:
        """近 `since_date`（含）以來的 (trade_date, percentile_rank) 清單，供 P4
        `ScanContext.buzz_percentile` 逐日序列使用。分位數本身已在 P1 `_write_buzz_async()`
        寫入時算好存進 `percentile_rank` 欄位（見 `upsert_buzz()`），這裡純粹取資料回填
        `ScanContext`，不重算——跟 `get_buzz_history()`（只回傳 `post_count`，給抓取階段
        自己算分位數用）刻意分成兩個方法，各自服務「寫入時算」與「讀取時查」兩種不同用途。"""
        stmt = text("""
            SELECT trade_date, percentile_rank FROM stock_discussion_buzz
             WHERE symbol = :symbol AND source = :source AND trade_date >= :since_date
        """)
        result = await self._s.execute(stmt, {"symbol": symbol, "source": source, "since_date": since_date})
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
