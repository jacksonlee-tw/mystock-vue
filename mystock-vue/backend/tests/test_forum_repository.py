"""
tests/test_forum_repository.py
`repositories/forum_repository.py` 的單元測試——沒有測試用 DB（見 CLAUDE.md），故 mock
`AsyncSession`，只驗證 SQL 參數組裝是否正確、回傳值轉換（Row -> dict）是否正確，不驗證 SQL
本身是否能在真實 Postgres 上執行。寫法比照 `tests/test_investment_note_tags.py` 的
`GetOrCreateTagsColorTests`：`unittest.IsolatedAsyncioTestCase` + `MagicMock`/`AsyncMock`。
"""
import unittest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

from repositories.forum_repository import ForumRepository


class _Row:
    """模擬 SQLAlchemy Row：repository 的 `_row_to_dict()` 只用得到 `_mapping`。"""

    def __init__(self, mapping: dict):
        self._mapping = mapping


def _repo():
    session = MagicMock()
    session.execute = AsyncMock()
    return ForumRepository(session), session


class UpsertPostTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_id_from_returning_clause_and_passes_all_fields(self):
        repo, session = _repo()
        result = MagicMock()
        result.scalar_one.return_value = 42
        session.execute.return_value = result

        post_id = await repo.upsert_post(
            source="ptt_stock", post_key="M.123.A.456", url="https://www.ptt.cc/bbs/Stock/M.123.A.456.html",
            title="標題", category="標的", author="someone", body_excerpt="內文摘要",
            push_count=48, boo_count=0, arrow_count=35,
            posted_at=datetime(2026, 9, 20, 12, 0), effective_trade_date=date(2026, 9, 21),
        )

        self.assertEqual(post_id, 42)
        session.execute.assert_awaited_once()
        stmt, params = session.execute.call_args.args
        self.assertIn("ON CONFLICT (source, post_key) DO UPDATE", str(stmt))
        self.assertEqual(params, {
            "source": "ptt_stock", "post_key": "M.123.A.456",
            "url": "https://www.ptt.cc/bbs/Stock/M.123.A.456.html", "title": "標題",
            "category": "標的", "author": "someone", "body_excerpt": "內文摘要",
            "push_count": 48, "boo_count": 0, "arrow_count": 35,
            "posted_at": datetime(2026, 9, 20, 12, 0), "effective_trade_date": date(2026, 9, 21),
        })

    async def test_conflict_update_does_not_touch_posted_at_or_sentiment_fields(self):
        # 重複抓取只更新推噓數/內文等會變動的欄位，不可覆蓋已評分的情緒結果或原始發布時間
        repo, session = _repo()
        result = MagicMock()
        result.scalar_one.return_value = 1
        session.execute.return_value = result

        await repo.upsert_post(
            source="ptt_stock", post_key="M.1.A.1", url="u", title="t",
            category=None, author=None, body_excerpt=None,
            push_count=0, boo_count=0, arrow_count=0,
            posted_at=datetime(2026, 1, 1), effective_trade_date=date(2026, 1, 1),
        )
        stmt, _ = session.execute.call_args.args
        sql = str(stmt)
        self.assertNotIn("posted_at = EXCLUDED", sql)
        self.assertNotIn("effective_trade_date = EXCLUDED", sql)
        self.assertNotIn("sentiment_score = EXCLUDED", sql)


class ReplacePostSymbolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_deletes_existing_then_inserts_each_symbol_in_order(self):
        repo, session = _repo()

        await repo.replace_post_symbols(1, [
            {"symbol": "2330", "matched_by": "code"},
            {"symbol": "0050", "matched_by": "name"},
        ])

        self.assertEqual(session.execute.await_count, 3)  # 1 刪除 + 2 插入

        delete_stmt, delete_params = session.execute.call_args_list[0].args
        self.assertIn("DELETE FROM forum_post_symbol", str(delete_stmt))
        self.assertEqual(delete_params, {"post_id": 1})

        insert1_stmt, insert1_params = session.execute.call_args_list[1].args
        self.assertIn("INSERT INTO forum_post_symbol", str(insert1_stmt))
        self.assertEqual(insert1_params, {"post_id": 1, "symbol": "2330", "matched_by": "code"})

        insert2_stmt, insert2_params = session.execute.call_args_list[2].args
        self.assertEqual(insert2_params, {"post_id": 1, "symbol": "0050", "matched_by": "name"})

    async def test_empty_symbol_list_only_deletes_no_stale_insert(self):
        repo, session = _repo()
        await repo.replace_post_symbols(1, [])
        session.execute.assert_awaited_once()
        _, delete_params = session.execute.call_args.args
        self.assertEqual(delete_params, {"post_id": 1})


class ListUnscoredTests(unittest.IsolatedAsyncioTestCase):
    async def test_converts_rows_to_dicts_and_passes_limit(self):
        repo, session = _repo()
        result = MagicMock()
        result.fetchall.return_value = [
            _Row({
                "id": 1, "title": "台積電噴出", "body_excerpt": "內文", "category": "標的",
                "push_count": 48, "boo_count": 0, "arrow_count": 35,
            }),
        ]
        session.execute.return_value = result

        rows = await repo.list_unscored(50)

        self.assertEqual(rows, [{
            "id": 1, "title": "台積電噴出", "body_excerpt": "內文", "category": "標的",
            "push_count": 48, "boo_count": 0, "arrow_count": 35,
        }])
        stmt, params = session.execute.call_args.args
        self.assertIn("sentiment_score IS NULL", str(stmt))
        self.assertEqual(params, {"limit": 50})

    async def test_empty_result_returns_empty_list(self):
        repo, session = _repo()
        result = MagicMock()
        result.fetchall.return_value = []
        session.execute.return_value = result
        self.assertEqual(await repo.list_unscored(10), [])


class UpdateSentimentTests(unittest.IsolatedAsyncioTestCase):
    async def test_passes_all_fields_to_update_statement(self):
        repo, session = _repo()
        await repo.update_sentiment(7, score=0.8, label="BULLISH", reason="營收年增創高", engine="gemini")

        stmt, params = session.execute.call_args.args
        self.assertIn("UPDATE forum_post", str(stmt))
        self.assertEqual(params, {
            "id": 7, "score": 0.8, "label": "BULLISH", "reason": "營收年增創高", "engine": "gemini",
        })


class ListTopDiscussedTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_grouped_rows_and_passes_trade_date_and_limit(self):
        repo, session = _repo()
        result = MagicMock()
        result.fetchall.return_value = [
            _Row({
                "symbol": "2330", "post_count": 3, "total_push": 120, "total_boo": 2,
                "avg_sentiment_score": 0.42, "representative_post_id": 9,
                "representative_title": "台積電噴出", "representative_url": "https://...",
            }),
        ]
        session.execute.return_value = result

        rows = await repo.list_top_discussed(trade_date=date(2026, 9, 21), limit=10)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "2330")
        self.assertEqual(rows[0]["post_count"], 3)
        self.assertEqual(rows[0]["representative_title"], "台積電噴出")
        stmt, params = session.execute.call_args.args
        sql = str(stmt)
        self.assertIn("GROUP BY fps.symbol", sql)
        self.assertIn("WHERE fp.effective_trade_date = :trade_date", sql)
        self.assertEqual(params, {"trade_date": date(2026, 9, 21), "limit": 10})

    async def test_no_discussion_that_day_returns_empty_list(self):
        repo, session = _repo()
        result = MagicMock()
        result.fetchall.return_value = []
        session.execute.return_value = result
        rows = await repo.list_top_discussed(trade_date=date(2026, 9, 21), limit=10)
        self.assertEqual(rows, [])


class PurgeExpiredTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_rowcount_and_uses_make_interval_not_string_concat(self):
        # make_interval() 而非 `:months || ' months'`：asyncpg 對 || 兩側型別無法推斷，
        # news_repository.py 的既有註解已記錄這個真實踩過的坑，這裡沿用同一寫法
        repo, session = _repo()
        result = MagicMock()
        result.rowcount = 5
        session.execute.return_value = result

        deleted = await repo.purge_expired(retention_months=6)

        self.assertEqual(deleted, 5)
        stmt, params = session.execute.call_args.args
        sql = str(stmt)
        self.assertIn("make_interval(months => :months)", sql)
        self.assertNotIn("||", sql)
        self.assertEqual(params, {"months": 6})

    async def test_none_rowcount_is_reported_as_zero(self):
        repo, session = _repo()
        result = MagicMock()
        result.rowcount = None
        session.execute.return_value = result
        deleted = await repo.purge_expired(retention_months=12)
        self.assertEqual(deleted, 0)


if __name__ == "__main__":
    unittest.main()
