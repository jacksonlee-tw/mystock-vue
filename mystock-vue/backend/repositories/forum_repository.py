"""
repositories/forum_repository.py
`forum_post` / `forum_post_symbol` 的唯一 SQL 入口（見
docs/16.AI技術分析/Phase7-PTT論壇情緒分析.md §5、CLAUDE.md「SQL 邊界」規範）。

比照 repositories/news_repository.py：建構子注入 AsyncSession、用 text() 寫原生 SQL（不用
ORM model），呼叫端自行決定何時 commit——本類別本身不 commit。

與既有 stock_news / stock_discussion_buzz 完全隔離（ADR-P7-03）：本檔案不與
NewsRepository 共用任何查詢或表，論壇資料的去重、評分、保留政策皆各自獨立，避免論壇雜訊
污染既有新聞情緒的品質。
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from db.session import _database_url

logger = logging.getLogger("mystock-backend")

# ── 給未來同步爬蟲模組（比照 services/news_fetcher.py）使用的橋接：獨立背景連線池 ──
# 比照 repositories/news_repository.py／stock_repository.py 各自維護一份不跟主 FastAPI
# event loop 共用的 engine，避免 run_async() 結束時的 dispose 波及主 loop 正在服務的請求。
# P0 階段尚無呼叫端（抓取器留待 P1），先備妥這組橋接，讓 P1 抓取器不需要再回頭補。
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
    """給未來同步爬蟲模組在 `run_async()` 包裹的協程內取用的 session context manager。"""
    session: AsyncSession = _get_bg_session_factory()()
    try:
        yield session
    finally:
        await session.close()


def run_async(coro):
    """讓未來同步的抓取器可以呼叫 async 版的 ForumRepository 方法，結束時 dispose 掉的是
    上面 _bg_engine（背景專用），不影響主 loop 的全域連線池。"""
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
    return dict(row._mapping)


class ForumRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    # ── forum_post ──────────────────────────────────────────────────
    async def upsert_post(
        self, *, source: str, post_key: str, url: str, title: str,
        category: Optional[str], author: Optional[str], body_excerpt: Optional[str],
        push_count: int, boo_count: int, arrow_count: int,
        posted_at: datetime, effective_trade_date: date,
    ) -> int:
        """依 `(source, post_key)` upsert 一篇貼文，回傳 `post_id`。

        衝突時只更新「重新抓取可能會變動」的欄位（標題、內文、推噓數等——PTT 文章的推文數
        會隨時間持續累加），`posted_at`／`effective_trade_date`／情緒欄位刻意不放進
        `DO UPDATE SET`，避免重複抓取覆蓋掉已評分的結果或竄改原始發布時間。"""
        stmt = text("""
            INSERT INTO forum_post
                   (source, post_key, url, title, category, author, body_excerpt,
                    push_count, boo_count, arrow_count, posted_at, effective_trade_date)
            VALUES (:source, :post_key, :url, :title, :category, :author, :body_excerpt,
                    :push_count, :boo_count, :arrow_count, :posted_at, :effective_trade_date)
            ON CONFLICT (source, post_key) DO UPDATE
               SET title = EXCLUDED.title,
                   category = EXCLUDED.category,
                   author = EXCLUDED.author,
                   body_excerpt = EXCLUDED.body_excerpt,
                   push_count = EXCLUDED.push_count,
                   boo_count = EXCLUDED.boo_count,
                   arrow_count = EXCLUDED.arrow_count
            RETURNING id
        """)
        result = await self._s.execute(stmt, {
            "source": source, "post_key": post_key, "url": url, "title": title,
            "category": category, "author": author, "body_excerpt": body_excerpt,
            "push_count": push_count, "boo_count": boo_count, "arrow_count": arrow_count,
            "posted_at": posted_at, "effective_trade_date": effective_trade_date,
        })
        return result.scalar_one()

    async def replace_post_symbols(self, post_id: int, symbols: list[dict]) -> None:
        """覆寫某篇貼文的標的關聯（先刪後插）。

        `symbols` 為 `[{"symbol": "2330", "matched_by": "code"}, ...]`；先刪後插而非逐筆
        diff，因為股號辨識邏輯改進後重新比對的結果可能整組不同，diff 的複雜度不划算，且
        單篇文章提及的標的數量很小（通常個位數），全量覆寫的成本可忽略。"""
        await self._s.execute(
            text("DELETE FROM forum_post_symbol WHERE post_id = :post_id"),
            {"post_id": post_id},
        )
        for item in symbols:
            await self._s.execute(
                text("""
                    INSERT INTO forum_post_symbol (post_id, symbol, matched_by)
                    VALUES (:post_id, :symbol, :matched_by)
                """),
                {"post_id": post_id, "symbol": item["symbol"], "matched_by": item["matched_by"]},
            )

    async def list_unscored(self, limit: int) -> list[dict]:
        """待評分佇列：`sentiment_score IS NULL` 的貼文，供未來 LLM 批次評分使用
        （P2，見規格書 §6）。帶回推噓數與分類，供評分時判斷文章語氣強度的輔助訊號。"""
        stmt = text("""
            SELECT id, title, body_excerpt, category, push_count, boo_count, arrow_count
              FROM forum_post
             WHERE sentiment_score IS NULL
             ORDER BY id
             LIMIT :limit
        """)
        result = await self._s.execute(stmt, {"limit": limit})
        return [_row_to_dict(r) for r in result.fetchall()]

    async def update_sentiment(
        self, post_id: int, *, score: float, label: str, reason: str, engine: str
    ) -> None:
        await self._s.execute(
            text("""
                UPDATE forum_post
                   SET sentiment_score = :score, sentiment_label = :label,
                       sentiment_reason = :reason, sentiment_engine = :engine
                 WHERE id = :id
            """),
            {"id": post_id, "score": score, "label": label, "reason": reason, "engine": engine},
        )

    async def list_top_discussed(self, *, trade_date: date, limit: int) -> list[dict]:
        """跨標的排行：依 `symbol` 聚合 `trade_date` 當日貼文數、推文總數、噓文總數、
        平均情緒分數與代表性貼文（推文數最高者）。

        既有 `NewsRepository` 的 13 個方法全部要求呼叫端先指定 `symbol=`，沒有任何跨股彙整
        查詢；本方法是「不知道要查哪一檔股票、反過來問『今天哪些股票被討論最多』」的查詢，
        用 `GROUP BY symbol` 一次查完，避免對每檔股票各查一次造成 N+1。`ARRAY_AGG(... ORDER
        BY push_count DESC)` 是 Postgres 在同一次 GROUP BY 裡取得「組內排序後第一筆」的慣用
        寫法，不需要額外一次 DISTINCT ON 子查詢或視窗函式。"""
        stmt = text("""
            SELECT fps.symbol,
                   COUNT(*) AS post_count,
                   COALESCE(SUM(fp.push_count), 0) AS total_push,
                   COALESCE(SUM(fp.boo_count), 0) AS total_boo,
                   AVG(fp.sentiment_score) AS avg_sentiment_score,
                   (ARRAY_AGG(fp.id ORDER BY fp.push_count DESC, fp.id DESC))[1]
                       AS representative_post_id,
                   (ARRAY_AGG(fp.title ORDER BY fp.push_count DESC, fp.id DESC))[1]
                       AS representative_title,
                   (ARRAY_AGG(fp.url ORDER BY fp.push_count DESC, fp.id DESC))[1]
                       AS representative_url
              FROM forum_post_symbol fps
              JOIN forum_post fp ON fp.id = fps.post_id
             WHERE fp.effective_trade_date = :trade_date
             GROUP BY fps.symbol
             ORDER BY post_count DESC, total_push DESC
             LIMIT :limit
        """)
        result = await self._s.execute(stmt, {"trade_date": trade_date, "limit": limit})
        return [_row_to_dict(r) for r in result.fetchall()]

    async def purge_expired(self, *, retention_months: int) -> int:
        """比照 news_repository.py 的 `purge_expired()`：逾 `retention_months` 個月的貼文
        刪除，`forum_post_symbol` 隨 `ON DELETE CASCADE` 一併清除。

        用 `make_interval(months => :months)` 而非 `:months || ' months'` 字串拼接——
        asyncpg 對 `||` 運算子兩側的參數型別無法推斷，會直接拋
        `DataError: invalid input for query argument`（news_repository.py 的既有註解已記錄
        這個真實踩過的坑，這裡直接沿用同一個寫法，不重蹈覆轍）。"""
        stmt = text("""
            DELETE FROM forum_post
             WHERE effective_trade_date < (CURRENT_DATE - make_interval(months => :months))
        """)
        result = await self._s.execute(stmt, {"months": retention_months})
        return result.rowcount or 0
