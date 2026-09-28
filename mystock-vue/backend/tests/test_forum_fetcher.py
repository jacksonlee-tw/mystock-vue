"""
tests/test_forum_fetcher.py
`services/forum_fetcher.py` 的單元測試（P1 抓取器，見
docs/01_Requirements/16.AI技術分析/Phase7-PTT論壇情緒分析.md §6）。

用 `tests/fixtures/ptt/` 下兩份真實抓下來的頁面驗證解析邏輯；網路請求一律 mock
（`requests.get` 從未被實際呼叫），DB 寫入也一律 mock（沒有測試用 DB，見 CLAUDE.md）。
寫法比照 `tests/test_forum_repository.py`：`unittest` + `unittest.mock`。
"""
import os
import unittest
from datetime import date, datetime
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

from services.forum_fetcher import (
    MAX_AUTHOR_CHARS,
    MAX_BODY_CHARS,
    MAX_CATEGORY_CHARS,
    MIN_SYMBOL_NAME_LENGTH,
    _build_name_index,
    _collect_target_date_articles,
    _extract_category,
    _extract_post_key,
    _extract_symbols,
    _fetch_and_build_post,
    _parse_article_page,
    _parse_index_page,
    _parse_md,
    _parse_nrec,
    _persist_posts_async,
    _strip_ptt_signature_lines,
    run_forum_fetch,
)

_FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "ptt")


def _read_fixture(name: str) -> str:
    with open(os.path.join(_FIXTURE_DIR, name), encoding="utf-8") as f:
        return f.read()


INDEX_HTML = _read_fixture("index_page.html")
ARTICLE_HTML = _read_fixture("article_biaodi.html")


# ── nrec 解析：不保證是數字，絕對不可 int() 直接轉 ──────────────────────────
class ParseNrecTests(unittest.TestCase):
    def test_plain_digit_string(self):
        self.assertEqual(_parse_nrec("13"), 13)

    def test_blank_means_below_threshold(self):
        self.assertIsNone(_parse_nrec(""))
        self.assertIsNone(_parse_nrec("   "))

    def test_explosion_marker(self):
        self.assertEqual(_parse_nrec("爆"), 100)

    def test_net_boo_markers_do_not_crash(self):
        self.assertEqual(_parse_nrec("X1"), -1)
        self.assertEqual(_parse_nrec("X9"), -9)
        self.assertEqual(_parse_nrec("XX"), -10)

    def test_unexpected_garbage_does_not_crash(self):
        self.assertIsNone(_parse_nrec("??"))


class ParseMdTests(unittest.TestCase):
    def test_parses_month_day(self):
        self.assertEqual(_parse_md(" 9/28"), (9, 28))

    def test_invalid_returns_none(self):
        self.assertIsNone(_parse_md("not-a-date"))


# ── 索引頁解析（真實 fixture：12 篇） ────────────────────────────────────
class ParseIndexPageTests(unittest.TestCase):
    def test_parses_all_non_deleted_posts_with_href_and_title(self):
        posts, _ = _parse_index_page(INDEX_HTML)
        self.assertEqual(len(posts), 12)
        first = posts[0]
        self.assertEqual(first["href"], "/bbs/Stock/M.1790556555.A.303.html")
        self.assertIn("GPU", first["title"])
        self.assertEqual(first["author"], "aapcao")
        self.assertEqual(first["date_md"], "9/28")
        self.assertEqual(first["nrec"], 13)

    def test_blank_nrec_entries_are_parsed_without_crashing(self):
        posts, _ = _parse_index_page(INDEX_HTML)
        blank_entries = [p for p in posts if p["nrec"] is None]
        self.assertGreaterEqual(len(blank_entries), 1)

    def test_re_prefixed_title_is_kept_verbatim_for_later_category_parsing(self):
        posts, _ = _parse_index_page(INDEX_HTML)
        re_posts = [p for p in posts if p["title"].startswith("Re:")]
        self.assertTrue(any("請益" in p["title"] for p in re_posts))

    def test_prev_page_href_extracted(self):
        _, prev_href = _parse_index_page(INDEX_HTML)
        self.assertEqual(prev_href, "/bbs/Stock/index10410.html")

    def test_deleted_post_without_anchor_is_skipped(self):
        html = """
        <div class="r-ent">
            <div class="nrec"></div>
            <div class="title">
                (本文已被刪除) [author1]
            </div>
            <div class="meta">
                <div class="author">-</div>
                <div class="date"> 9/28</div>
            </div>
        </div>
        <div class="r-ent">
            <div class="nrec"><span class="hl f3">5</span></div>
            <div class="title">
                <a href="/bbs/Stock/M.1.A.1.html">[閒聊] still here</a>
            </div>
            <div class="meta">
                <div class="author">someone</div>
                <div class="date"> 9/28</div>
            </div>
        </div>
        """
        posts, _ = _parse_index_page(html)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["href"], "/bbs/Stock/M.1.A.1.html")


# ── 文章頁解析（真實 fixture：[標的] 生達1720…） ─────────────────────────
class ParseArticlePageTests(unittest.TestCase):
    def setUp(self):
        self.parsed = _parse_article_page(ARTICLE_HTML)

    def test_parses_title_author_and_real_timestamp(self):
        self.assertEqual(self.parsed["title"], "[標的] 生達1720、邦特4107、儒鴻1476、宏全9939")
        self.assertEqual(self.parsed["author"], "tooth9")
        self.assertEqual(self.parsed["posted_at"], datetime(2026, 9, 27, 0, 37, 5))

    def test_body_contains_real_content_between_meta_and_first_push(self):
        self.assertIn("生達1720", self.parsed["body"])
        self.assertIn("儒鴻", self.parsed["body"])
        # meta 區塊本身（作者/看板/標題/時間）不該混入內文
        self.assertNotIn("tooth9", self.parsed["body"])

    def test_push_boo_arrow_counts_match_manual_tally(self):
        # 規格書 ADR-P7-02 實測數字：推 48／噓 0／→ 35，共 83 則
        self.assertEqual(self.parsed["push_count"], 48)
        self.assertEqual(self.parsed["boo_count"], 0)
        self.assertEqual(self.parsed["arrow_count"], 35)

    def test_missing_main_content_returns_none(self):
        self.assertIsNone(_parse_article_page("<html><body>空頁面</body></html>"))


# ── post_key 抽取 ────────────────────────────────────────────────────────
class ExtractPostKeyTests(unittest.TestCase):
    def test_from_relative_href(self):
        self.assertEqual(_extract_post_key("/bbs/Stock/M.1790440627.A.4F7.html"), "M.1790440627.A.4F7")

    def test_from_full_url(self):
        url = "https://www.ptt.cc/bbs/Stock/M.1790440627.A.4F7.html"
        self.assertEqual(_extract_post_key(url), "M.1790440627.A.4F7")

    def test_no_match_returns_none(self):
        self.assertIsNone(_extract_post_key("/bbs/Stock/index.html"))


# ── category 解析 ────────────────────────────────────────────────────────
class ExtractCategoryTests(unittest.TestCase):
    def test_plain_prefix(self):
        self.assertEqual(_extract_category("[標的] 生達1720、邦特4107"), "標的")

    def test_re_prefix_still_parses_bracket(self):
        self.assertEqual(_extract_category("Re: [請益] 基本面投資如何驗證自己錯了"), "請益")

    def test_no_bracket_returns_none(self):
        self.assertIsNone(_extract_category("完全沒有分類標記的標題"))


# ── 股號抽取：code ∪ name 雙路比對 ────────────────────────────────────────
class ExtractSymbolsTests(unittest.TestCase):
    def test_code_path_hit(self):
        result = _extract_symbols("台積電2330今天大漲", code_set={"2330"}, name_index={})
        self.assertEqual(result, [{"symbol": "2330", "matched_by": "code"}])

    def test_name_path_hit(self):
        result = _extract_symbols("鴻海今天大漲", code_set=set(), name_index={"鴻海": "2317"})
        self.assertEqual(result, [{"symbol": "2317", "matched_by": "name"}])

    def test_multiple_symbols_in_one_post(self):
        result = _extract_symbols(
            "生達1720、邦特4107、儒鴻1476、宏全9939",
            code_set={"1720", "4107", "1476", "9939"}, name_index={},
        )
        symbols = {r["symbol"] for r in result}
        self.assertEqual(symbols, {"1720", "4107", "1476", "9939"})

    def test_no_match_returns_empty_list(self):
        result = _extract_symbols("完全沒有提到任何標的的閒聊內容", code_set={"2330"}, name_index={"鴻海": "2317"})
        self.assertEqual(result, [])

    def test_same_symbol_matched_by_both_paths_is_not_duplicated(self):
        result = _extract_symbols("鴻海2317大漲", code_set={"2317"}, name_index={"鴻海": "2317"})
        self.assertEqual(len(result), 1)


class BuildNameIndexTests(unittest.TestCase):
    # 舊版規則（整批排除「是另一檔標的全名子字串」的短名稱）已被真實資料實測推翻——見
    # services/forum_fetcher.py `_build_name_index()` docstring：拿台股全代號主檔
    # （2447 檔）量測，舊規則全域丟棄率僅 4.15%（100/2412），但使用者指定的 23 檔熱門股
    # 裡有 10 檔（43%：長榮／台塑／南亞／中鋼／統一／華新／聯電／國泰金／富邦金／台泥）
    # 整批消失，因為它們剛好是冷門子公司／特別股／ETF 全名的子字串。改採本測試類別
    # 驗證的新規則：短名稱一律留在比對表裡，是否命中留給 `_extract_symbols()` 依「同一段
    # 文字裡最長優先」判斷（見下面 `ExtractSymbolsLongestMatchTests`）。
    def test_short_name_that_is_substring_of_another_name_is_kept_in_index(self):
        rows = [
            {"symbol": "1101", "name": "台泥"},
            {"symbol": "9999", "name": "台泥工程"},
        ]
        index = _build_name_index(rows)
        self.assertEqual(index.get("台泥"), "1101")
        self.assertEqual(index.get("台泥工程"), "9999")

    def test_unambiguous_names_are_kept(self):
        rows = [{"symbol": "2317", "name": "鴻海"}, {"symbol": "2330", "name": "台積電"}]
        index = _build_name_index(rows)
        self.assertEqual(index, {"鴻海": "2317", "台積電": "2330"})

    def test_names_shorter_than_minimum_are_dropped(self):
        rows = [{"symbol": "9999", "name": "x" * (MIN_SYMBOL_NAME_LENGTH - 1)}]
        index = _build_name_index(rows)
        self.assertEqual(index, {})


class ExtractSymbolsLongestMatchTests(unittest.TestCase):
    """`_extract_symbols()` 的「同一段文字裡最長優先」防護：取代舊版整批丟棄短名稱的
    規則，數字依據見 `BuildNameIndexTests` 類別開頭的說明與 `_build_name_index()`
    docstring。"""

    def test_short_name_alone_still_matches_when_no_longer_name_present(self):
        # 「長榮」單獨出現（沒有「長榮航」）時，命中率是本片要拉高的重點，不該被犧牲。
        name_index = _build_name_index([
            {"symbol": "2603", "name": "長榮"},
            {"symbol": "2618", "name": "長榮航"},
        ])
        result = _extract_symbols("長榮今天法人買超", code_set=set(), name_index=name_index)
        self.assertEqual(result, [{"symbol": "2603", "matched_by": "name"}])

    def test_short_name_is_shadowed_when_longer_containing_name_also_present(self):
        name_index = _build_name_index([
            {"symbol": "1101", "name": "台泥"},
            {"symbol": "9999", "name": "台泥工程"},
        ])
        result = _extract_symbols("台泥工程今天發包", code_set=set(), name_index=name_index)
        # 只會命中較長的「台泥工程」(9999)，短名稱「台泥」(1101) 的命中被同段文字裡
        # 更長的命中蓋過，不會誤判成台泥自己那檔
        self.assertEqual(result, [{"symbol": "9999", "matched_by": "name"}])

    def test_both_short_and_long_names_can_match_independently_in_same_post(self):
        # 一篇文章同時單獨提到「長榮」與「台泥工程」（互不包含）時，兩者都該正常命中。
        name_index = _build_name_index([
            {"symbol": "2603", "name": "長榮"},
            {"symbol": "2618", "name": "長榮航"},
            {"symbol": "1101", "name": "台泥"},
            {"symbol": "9999", "name": "台泥工程"},
        ])
        result = _extract_symbols(
            "長榮今天大漲，台泥工程也發包了", code_set=set(), name_index=name_index,
        )
        symbols = {r["symbol"] for r in result}
        self.assertEqual(symbols, {"2603", "9999"})


# ── 簽名檔行剝除（問題 3：截斷前先剝掉站方樣板，別浪費截斷配額） ───────────
class StripPttSignatureLinesTests(unittest.TestCase):
    def test_strips_station_and_url_lines(self):
        body = "內文第一行\n※ 發信站: 批踢踢實業坊(ptt.cc), 來自: 1.2.3.4 (臺灣)\n※ 文章網址: https://www.ptt.cc/bbs/Stock/M.1.A.1.html\n內文最後一行"
        result = _strip_ptt_signature_lines(body)
        self.assertNotIn("發信站", result)
        self.assertNotIn("文章網址", result)
        self.assertIn("內文第一行", result)
        self.assertIn("內文最後一行", result)

    def test_strips_edit_marker_line(self):
        body = "心得內文\n※ 編輯: someone (1.2.3.4), 09/27/2026 12:00:00"
        result = _strip_ptt_signature_lines(body)
        self.assertNotIn("編輯", result)
        self.assertIn("心得內文", result)

    def test_body_without_signature_lines_is_unchanged(self):
        body = "完全沒有簽名檔的內文"
        self.assertEqual(_strip_ptt_signature_lines(body), body)


# ── MAX_BODY_CHARS 截斷 ───────────────────────────────────────────────────
class FetchAndBuildPostTests(unittest.TestCase):
    def _article_html(self, body_text: str, *, title: str = "[心得] 測試文章", time_str: str = "Sun Sep 27 00:37:05 2026"):
        return f"""
        <div id="main-content">
            <div class="article-metaline"><span class="article-meta-tag">作者</span><span class="article-meta-value">tester (test)</span></div>
            <div class="article-metaline-right"><span class="article-meta-tag">看板</span><span class="article-meta-value">Stock</span></div>
            <div class="article-metaline"><span class="article-meta-tag">標題</span><span class="article-meta-value">{title}</span></div>
            <div class="article-metaline"><span class="article-meta-tag">時間</span><span class="article-meta-value">{time_str}</span></div>
            {body_text}
            <div class="push"><span class="push-tag">推 </span><span class="push-userid">u</span><span class="push-content">: ok</span></div>
        </div>
        """

    @patch("services.forum_fetcher._save_raw_snapshot", return_value=None)
    @patch("services.forum_fetcher._fetch_html")
    def test_long_body_is_truncated_to_max_body_chars(self, mock_fetch, _mock_snapshot):
        long_body = "字" * (MAX_BODY_CHARS * 2)
        mock_fetch.return_value = self._article_html(long_body)

        post = _fetch_and_build_post(
            "/bbs/Stock/M.1.A.1.html", code_set=set(), name_index={},
            is_trading_day=lambda d: True,
        )

        self.assertIsNotNone(post)
        self.assertEqual(len(post["body_excerpt"]), MAX_BODY_CHARS)

    @patch("services.forum_fetcher._save_raw_snapshot", return_value=None)
    @patch("services.forum_fetcher._fetch_html")
    def test_short_body_is_kept_as_is(self, mock_fetch, _mock_snapshot):
        mock_fetch.return_value = self._article_html("短內文")

        post = _fetch_and_build_post(
            "/bbs/Stock/M.1.A.1.html", code_set=set(), name_index={},
            is_trading_day=lambda d: True,
        )

        self.assertIsNotNone(post)
        self.assertLess(len(post["body_excerpt"]), MAX_BODY_CHARS)

    @patch("services.forum_fetcher._save_raw_snapshot", return_value=None)
    @patch("services.forum_fetcher._fetch_html")
    def test_signature_lines_are_stripped_before_truncation(self, mock_fetch, _mock_snapshot):
        # 問題 3：簽名檔行必須在截斷「之前」剝除，否則短文會被這幾行站方樣板佔掉大半配額。
        body_with_signature = (
            "短內文\n"
            "※ 發信站: 批踢踢實業坊(ptt.cc), 來自: 1.2.3.4 (臺灣)\n"
            "※ 文章網址: https://www.ptt.cc/bbs/Stock/M.1.A.1.html"
        )
        mock_fetch.return_value = self._article_html(body_with_signature)

        post = _fetch_and_build_post(
            "/bbs/Stock/M.1.A.1.html", code_set=set(), name_index={},
            is_trading_day=lambda d: True,
        )

        self.assertIsNotNone(post)
        self.assertNotIn("發信站", post["body_excerpt"])
        self.assertNotIn("文章網址", post["body_excerpt"])
        self.assertIn("短內文", post["body_excerpt"])

    @patch("services.forum_fetcher._save_raw_snapshot", return_value=None)
    @patch("services.forum_fetcher._fetch_html")
    def test_long_category_is_truncated_to_db_column_limit(self, mock_fetch, _mock_snapshot):
        # 問題 1：category 對應 forum_post.category VARCHAR(10)，標題分類是使用者自由輸入，
        # 沒有長度上限，落地前必須截斷，否則 asyncpg 會拋 StringDataRightTruncation。
        long_category = "小小上班族的第一次進場心得"
        self.assertGreater(len(long_category), MAX_CATEGORY_CHARS)
        mock_fetch.return_value = self._article_html("內文", title=f"[{long_category}] 測試標題")

        post = _fetch_and_build_post(
            "/bbs/Stock/M.1.A.1.html", code_set=set(), name_index={},
            is_trading_day=lambda d: True,
        )

        self.assertIsNotNone(post)
        self.assertEqual(post["category"], long_category[:MAX_CATEGORY_CHARS])
        self.assertLessEqual(len(post["category"]), MAX_CATEGORY_CHARS)

    @patch("services.forum_fetcher._save_raw_snapshot", return_value=None)
    @patch("services.forum_fetcher._fetch_html")
    def test_long_author_value_is_truncated_to_db_column_limit(self, mock_fetch, _mock_snapshot):
        # 問題 1：author 對應 forum_post.author VARCHAR(40)。`_parse_article_page()` 用
        # `author_raw.split(" ")[0]` 取 userid 部分（正常情況下 id 本身不長），但當作者
        # meta 沒有一般 ASCII 空白可切（例如缺少「(暱稱)」區段），整段字串會原封不動當成
        # author 回傳、沒有長度上限——這裡直接構造一個沒有空白可切的超長單一 token，
        # 驗證落地前仍會被截斷，不依賴 `_parse_article_page()` 的切法細節。
        long_author_value = "無空格暱稱" * 20
        self.assertGreater(len(long_author_value), MAX_AUTHOR_CHARS)
        html = f"""
        <div id="main-content">
            <div class="article-metaline"><span class="article-meta-tag">作者</span><span class="article-meta-value">{long_author_value}</span></div>
            <div class="article-metaline-right"><span class="article-meta-tag">看板</span><span class="article-meta-value">Stock</span></div>
            <div class="article-metaline"><span class="article-meta-tag">標題</span><span class="article-meta-value">[心得] 測試</span></div>
            <div class="article-metaline"><span class="article-meta-tag">時間</span><span class="article-meta-value">Sun Sep 27 00:37:05 2026</span></div>
            內文
            <div class="push"><span class="push-tag">推 </span><span class="push-userid">u</span><span class="push-content">: ok</span></div>
        </div>
        """
        mock_fetch.return_value = html

        post = _fetch_and_build_post(
            "/bbs/Stock/M.1.A.1.html", code_set=set(), name_index={},
            is_trading_day=lambda d: True,
        )

        self.assertIsNotNone(post)
        self.assertEqual(post["author"], long_author_value[:MAX_AUTHOR_CHARS])
        self.assertLessEqual(len(post["author"]), MAX_AUTHOR_CHARS)

    @patch("services.forum_fetcher._save_raw_snapshot", return_value=None)
    @patch("services.forum_fetcher._fetch_html")
    def test_post_with_no_symbols_still_builds_a_record(self, mock_fetch, _mock_snapshot):
        mock_fetch.return_value = self._article_html("完全沒有提到任何標的的內容", title="[閒聊] 純聊天")

        post = _fetch_and_build_post(
            "/bbs/Stock/M.1.A.1.html", code_set={"2330"}, name_index={"鴻海": "2317"},
            is_trading_day=lambda d: True,
        )

        self.assertIsNotNone(post)
        self.assertEqual(post["symbols"], [])
        self.assertEqual(post["category"], "閒聊")

    @patch("services.forum_fetcher._fetch_html", return_value=None)
    def test_network_failure_returns_none(self, _mock_fetch):
        post = _fetch_and_build_post(
            "/bbs/Stock/M.1.A.1.html", code_set=set(), name_index={}, is_trading_day=lambda d: True,
        )
        self.assertIsNone(post)

    def test_href_without_post_key_returns_none_without_network_call(self):
        with patch("services.forum_fetcher._fetch_html") as mock_fetch:
            post = _fetch_and_build_post(
                "/bbs/Stock/index.html", code_set=set(), name_index={}, is_trading_day=lambda d: True,
            )
            self.assertIsNone(post)
            mock_fetch.assert_not_called()


_OLDER_PAGE_HTML = """
<html><body>
<div class="action-bar">
    <a class="btn wide" href="/bbs/Stock/index10409.html">&lsaquo; 上頁</a>
</div>
<div class="r-ent">
    <div class="nrec"><span class="hl f3">1</span></div>
    <div class="title"><a href="/bbs/Stock/M.2.A.2.html">[閒聊] 昨天的閒聊</a></div>
    <div class="meta">
        <div class="author">someone</div>
        <div class="date"> 9/27</div>
    </div>
</div>
</body></html>
"""


# ── 索引頁翻頁收集候選（網路一律 mock） ───────────────────────────────────
class CollectTargetDateArticlesTests(unittest.TestCase):
    @patch("services.forum_fetcher._save_raw_snapshot", return_value=None)
    @patch("services.forum_fetcher._throttle", return_value=None)
    @patch("services.forum_fetcher._fetch_html")
    def test_stops_paging_once_oldest_post_is_before_target_date(self, mock_fetch, _throttle, _snapshot):
        # 第一頁最舊一篇（posts[0]，即頁面第一篇）仍是目標日 9/28，故會繼續往前翻一頁；
        # 第二頁最舊一篇是 9/27，早於目標日，翻頁應在抓完第二頁後停止，不會再抓第三頁。
        mock_fetch.side_effect = [INDEX_HTML, _OLDER_PAGE_HTML]

        candidates = _collect_target_date_articles(date(2026, 9, 28), max_pages=8)

        self.assertTrue(all(_parse_md(c["date_md"]) == (9, 28) for c in candidates))
        self.assertEqual(mock_fetch.call_count, 2)

    @patch("services.forum_fetcher._fetch_html", return_value=None)
    def test_network_failure_returns_empty_list_without_crashing(self, _mock_fetch):
        self.assertEqual(_collect_target_date_articles(date(2026, 9, 28)), [])


# ── 落地：抽不到標的仍要寫入 forum_post ───────────────────────────────────
def _make_savepoint_session() -> AsyncMock:
    """建一個能正確模擬 SQLAlchemy `AsyncSession.begin_nested()` 用法的 mock session。

    真正的 `begin_nested()` 是**同步**呼叫、回傳一個可以 `async with` 的物件（不是要
    `await` 的 coroutine）；若讓 `session` 整個是 `AsyncMock()`，子屬性會預設也變成
    `AsyncMock`，`session.begin_nested()` 就會變成回傳 coroutine，塞進 `async with` 會直接
    炸掉——這裡手動覆寫成正確的形狀（`MagicMock` 包一個有 `__aenter__`/`__aexit__` 的
    `async with` 物件），讓測試貼近真實 SQLAlchemy 行為。`__aexit__` 回傳 `False`：savepoint
    本身只負責 rollback 到該點，例外仍要往外傳，才會被 `_persist_posts_async()` 的
    `try/except` 接住。"""
    session = AsyncMock()
    nested_cm = MagicMock()
    nested_cm.__aenter__ = AsyncMock(return_value=None)
    nested_cm.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested_cm)
    return session


def _make_post(post_key: str = "M.1.A.1", **overrides) -> Dict[str, Any]:
    post = {
        "source": "ptt_stock", "post_key": post_key, "url": "u", "title": "t",
        "category": None, "author": None, "body_excerpt": None,
        "push_count": 0, "boo_count": 0, "arrow_count": 0,
        "posted_at": datetime(2026, 9, 28), "effective_trade_date": date(2026, 9, 28),
        "symbols": [],
    }
    post.update(overrides)
    return post


class PersistPostsAsyncTests(unittest.IsolatedAsyncioTestCase):
    @patch("services.forum_fetcher.ForumRepository")
    @patch("services.forum_fetcher.get_background_session")
    async def test_post_without_symbols_is_upserted_but_symbols_not_replaced(self, mock_get_session, mock_repo_cls):
        session = _make_savepoint_session()
        mock_get_session.return_value.__aenter__.return_value = session
        mock_get_session.return_value.__aexit__.return_value = False
        repo = mock_repo_cls.return_value
        repo.upsert_post = AsyncMock(return_value=1)
        repo.replace_post_symbols = AsyncMock()

        result = await _persist_posts_async([_make_post()])

        repo.upsert_post.assert_awaited_once()
        repo.replace_post_symbols.assert_not_awaited()
        self.assertEqual(result, {"posts_written": 1, "symbol_links_written": 0, "posts_failed": 0})

    @patch("services.forum_fetcher.ForumRepository")
    @patch("services.forum_fetcher.get_background_session")
    async def test_post_with_symbols_replaces_symbol_links(self, mock_get_session, mock_repo_cls):
        session = _make_savepoint_session()
        mock_get_session.return_value.__aenter__.return_value = session
        mock_get_session.return_value.__aexit__.return_value = False
        repo = mock_repo_cls.return_value
        repo.upsert_post = AsyncMock(return_value=7)
        repo.replace_post_symbols = AsyncMock()

        result = await _persist_posts_async([_make_post(
            category="標的", author="a", body_excerpt="b", push_count=1,
            symbols=[{"symbol": "2330", "matched_by": "code"}],
        )])

        repo.replace_post_symbols.assert_awaited_once_with(7, [{"symbol": "2330", "matched_by": "code"}])
        self.assertEqual(result, {"posts_written": 1, "symbol_links_written": 1, "posts_failed": 0})

    @patch("services.forum_fetcher.ForumRepository")
    @patch("services.forum_fetcher.get_background_session")
    async def test_one_failing_post_does_not_prevent_others_from_being_persisted(
        self, mock_get_session, mock_repo_cls,
    ):
        # 問題 1 的核心迴歸測試：整批 3 篇裡第 2 篇寫入失敗（模擬 StringDataRightTruncation
        # 之類未預期的 DB 例外），其餘兩篇仍要成功落地、整批不能一起回滾。
        session = _make_savepoint_session()
        mock_get_session.return_value.__aenter__.return_value = session
        mock_get_session.return_value.__aexit__.return_value = False
        repo = mock_repo_cls.return_value
        repo.upsert_post = AsyncMock(side_effect=[1, RuntimeError("simulated StringDataRightTruncation"), 3])
        repo.replace_post_symbols = AsyncMock()

        posts = [_make_post(post_key="M.1.A.1"), _make_post(post_key="M.2.A.2"), _make_post(post_key="M.3.A.3")]
        result = await _persist_posts_async(posts)

        self.assertEqual(repo.upsert_post.await_count, 3)
        self.assertEqual(result, {"posts_written": 2, "symbol_links_written": 0, "posts_failed": 1})
        session.commit.assert_awaited_once()

    @patch("services.forum_fetcher.ForumRepository")
    @patch("services.forum_fetcher.get_background_session")
    async def test_all_posts_failing_still_commits_without_raising(self, mock_get_session, mock_repo_cls):
        session = _make_savepoint_session()
        mock_get_session.return_value.__aenter__.return_value = session
        mock_get_session.return_value.__aexit__.return_value = False
        repo = mock_repo_cls.return_value
        repo.upsert_post = AsyncMock(side_effect=RuntimeError("boom"))
        repo.replace_post_symbols = AsyncMock()

        result = await _persist_posts_async([_make_post("M.1.A.1"), _make_post("M.2.A.2")])

        self.assertEqual(result, {"posts_written": 0, "symbol_links_written": 0, "posts_failed": 2})
        session.commit.assert_awaited_once()


# ── run_forum_fetch 端到端組裝（全部 mock，不觸網／不觸 DB） ────────────────
class RunForumFetchTests(unittest.TestCase):
    # `_persist_posts_async` 是 async def，`@patch` 預設會自動幫它套用 AsyncMock；但這裡
    # `run_async` 本身也整個被 mock 掉、不會真的 await 任何東西，若讓 `_persist_posts_async`
    # 仍是 AsyncMock，呼叫它會產生一個真的 coroutine 物件、永遠沒人 await，被 gc 時 pytest
    # 會噴 RuntimeWarning。改用 `new_callable=MagicMock` 讓它直接回傳一般值，不產生 coroutine。
    @patch("services.forum_fetcher._persist_posts_async", new_callable=MagicMock)
    @patch("services.forum_fetcher.run_async")
    @patch("services.forum_fetcher._fetch_and_build_post")
    @patch("services.forum_fetcher._collect_target_date_articles")
    @patch("services.forum_fetcher._is_trading_day_checker")
    @patch("services.forum_fetcher._known_symbol_index")
    @patch("services.forum_fetcher._throttle", return_value=None)
    def test_assembles_summary_dict_from_collected_and_written_posts(
        self, _throttle, mock_known, mock_trading_day, mock_collect, mock_build, mock_run_async, mock_persist,
    ):
        mock_known.return_value = (set(), {})
        mock_trading_day.return_value = lambda d: True
        mock_collect.return_value = [{"href": "/bbs/Stock/M.1.A.1.html", "date_md": "9/28"}]
        mock_build.return_value = {
            "source": "ptt_stock", "post_key": "M.1.A.1", "url": "u", "title": "t",
            "category": None, "author": None, "body_excerpt": None,
            "push_count": 0, "boo_count": 0, "arrow_count": 0,
            "posted_at": datetime(2026, 9, 28), "effective_trade_date": date(2026, 9, 28),
            "symbols": [],
        }
        mock_run_async.return_value = {"posts_written": 1, "symbol_links_written": 0, "posts_failed": 0}

        result = run_forum_fetch(trigger_type="manual", target_date=date(2026, 9, 28))

        self.assertEqual(result["candidates_found"], 1)
        self.assertEqual(result["posts_written"], 1)
        self.assertEqual(result["posts_failed"], 0)
        self.assertEqual(result["trigger_type"], "manual")
        mock_run_async.assert_called_once()

    @patch("services.forum_fetcher._persist_posts_async", new_callable=MagicMock)
    @patch("services.forum_fetcher.run_async")
    @patch("services.forum_fetcher._fetch_and_build_post")
    @patch("services.forum_fetcher._collect_target_date_articles")
    @patch("services.forum_fetcher._is_trading_day_checker")
    @patch("services.forum_fetcher._known_symbol_index")
    @patch("services.forum_fetcher._throttle", return_value=None)
    def test_summary_dict_surfaces_posts_failed_count(
        self, _throttle, mock_known, mock_trading_day, mock_collect, mock_build, mock_run_async, mock_persist,
    ):
        # 問題 1 的驗收：write_result 帶回的 posts_failed 要往上傳到 run_forum_fetch() 的
        # 回傳值，呼叫端（未來的 API／排程）才看得到「這批有幾篇落地失敗」。
        mock_known.return_value = (set(), {})
        mock_trading_day.return_value = lambda d: True
        mock_collect.return_value = [{"href": "/bbs/Stock/M.1.A.1.html", "date_md": "9/28"}]
        mock_build.return_value = {
            "source": "ptt_stock", "post_key": "M.1.A.1", "url": "u", "title": "t",
            "category": None, "author": None, "body_excerpt": None,
            "push_count": 0, "boo_count": 0, "arrow_count": 0,
            "posted_at": datetime(2026, 9, 28), "effective_trade_date": date(2026, 9, 28),
            "symbols": [],
        }
        mock_run_async.return_value = {"posts_written": 0, "symbol_links_written": 0, "posts_failed": 1}

        result = run_forum_fetch(trigger_type="manual", target_date=date(2026, 9, 28))

        self.assertEqual(result["posts_failed"], 1)

    @patch("services.forum_fetcher._collect_target_date_articles", side_effect=RuntimeError("boom"))
    @patch("services.forum_fetcher._is_trading_day_checker", return_value=lambda d: True)
    @patch("services.forum_fetcher._known_symbol_index", return_value=(set(), {}))
    def test_failure_marks_fetch_status_failed_and_reraises(self, _known, _trading_day, _collect):
        with self.assertRaises(RuntimeError):
            run_forum_fetch(target_date=date(2026, 9, 28))
        from services.forum_fetcher import fetch_status
        self.assertEqual(fetch_status.status, "error")


if __name__ == "__main__":
    unittest.main()
