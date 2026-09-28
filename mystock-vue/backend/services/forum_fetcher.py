"""
services/forum_fetcher.py
PTT Stock 板貼文抓取（P1，docs/01_Requirements/16.AI技術分析/Phase7-PTT論壇情緒分析.md §6 P1，
ADR-P7-02／ADR-P7-03）。

本片只做「抓取＋解析＋股號比對＋落地」，**不含任何 LLM 情緒評分**（P2 才做），寫入
`forum_post` 的 `sentiment_*` 欄位一律留 NULL（schema 本來就允許缺值，見 `forum_repository.py`
docstring）。

刻意與 `services/news_fetcher.py` 完全隔離、自成一份（ADR-P7-03）：HTTP 存取／節流／原始
快照落地的寫法比照該檔案的既有慣例，但**不 import 該模組的任何函式**——`news_fetcher.py`
的 `fetch_ptt_stock()` 仍服務既有的 `stock_discussion_buzz` 管線（只看標題），本檔案是
完全獨立的第二條 PTT 抓取管線（抓內文＋推文＋雙路股號比對），兩者不應互相牽動。

流程（`run_forum_fetch()`）：
    1. 從索引頁往前翻頁，用「M/D 粗篩」收集目標日期可能的文章連結（索引頁沒有年份，
       只能拿來粗篩／決定翻頁停在哪，見 `_collect_target_date_articles()` docstring）。
    2. 逐篇抓文章頁，解析真實時間戳、內文、推噓則數逐則計數。
    3. 依 code∪name 雙路比對抽取標的（見 `_extract_symbols()`）。
    4. 透過 `ForumRepository.upsert_post()` / `replace_post_symbols()` 落地。
"""
from __future__ import annotations

import logging
import os
import random
import re
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from config import DATA_DIR
from indicators.news_time import effective_trade_date, is_weekday_trading_day
from repositories.forum_repository import ForumRepository, get_background_session, run_async
from repositories.stock_repository import StockRepository
from services.fetcher import FetchStatusManager

logger = logging.getLogger("mystock-backend")

fetch_status = FetchStatusManager()

# ── HTTP 存取（照抄 services/news_fetcher.py 的既有慣例，不 import，維持管線隔離）──────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
_OVER18_COOKIES = {"over18": "1"}  # PTT 18 歲同意頁，見 news_fetcher.py 既有先例

_BASE_URL = "https://www.ptt.cc"
_INDEX_URL = f"{_BASE_URL}/bbs/Stock/index.html"

_FORUM_RAW_DIR = os.path.join(DATA_DIR, "_forum", "raw", "ptt_stock")

# 內文截斷長度。獨立具名常數，P2 做 prompt injection 防護時很可能需要調整這個值，
# 拆成常數方便之後直接改這一處，不必到處找魔術數字。
MAX_BODY_CHARS = 800

# 落地前的欄位長度上限，對應 db/migration/V25__Create_forum_sentiment_tables.sql 的
# forum_post.category VARCHAR(10) / forum_post.author VARCHAR(40)。PTT 標題分類與作者
# 暱稱都是使用者自由輸入、沒有長度保證（例如標題 `[小小上班族的第一次進場心得]` 分類
# 就有 13 字，作者 meta 的 `暱稱` 部分更是完全自訂），若不在寫入前截斷，asyncpg 會直接
# 拋 StringDataRightTruncation——改 V25 的欄位長度時要一併改這兩個常數。
MAX_CATEGORY_CHARS = 10
MAX_AUTHOR_CHARS = 40

# 公司名稱短於此長度一律不用於比對，避免單字/雙字通用詞造成大量雜訊。
MIN_SYMBOL_NAME_LENGTH = 2

# PTT 站方自動附加、對情緒分析毫無價值的簽名檔行前綴，落地前剝除（見
# `_strip_ptt_signature_lines()`），避免佔掉 MAX_BODY_CHARS 的截斷額度。
_SIGNATURE_LINE_PREFIXES = ("※ 發信站:", "※ 文章網址:", "※ 編輯:")

_SYMBOL_CODE_PATTERN = re.compile(r"\d{4,6}[A-Z]?")
_POST_KEY_PATTERN = re.compile(r"(M\.\d+\.A\.\w+)\.html")
_CATEGORY_PATTERN = re.compile(r"^(?:Re:\s*)?\[([^\]]+)\]")
_ARTICLE_TIME_FORMAT = "%a %b %d %H:%M:%S %Y"


def _throttle(rate_limit_seconds: tuple = (1.0, 2.5)) -> None:
    """照抄 services/news_fetcher.py `_throttle()` 的寫法（刻意不 import，見模組頂端
    ADR-P7-03 隔離說明）。PTT Stock 板每日文章量小（20~40 篇），隨機延遲即足夠，不需要
    比照 TWSE 逐日爬蟲那套行程級自適應限流器。"""
    time.sleep(random.uniform(*rate_limit_seconds))


def _save_raw_snapshot(name: str, html: str) -> Optional[str]:
    """照抄 services/news_fetcher.py `_save_raw_snapshot()` 的兩段式落地慣例：原始頁面先
    落地成檔案，之後解析或寫入 Postgres 失敗時可以重跑，不必重新對 PTT 發請求。"""
    try:
        os.makedirs(_FORUM_RAW_DIR, exist_ok=True)
        path = os.path.join(_FORUM_RAW_DIR, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S%f')}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return path
    except Exception as e:
        logger.warning(f"[forum_fetcher] 原始快照落地失敗 ({name}): {e}")
        return None


def _fetch_html(url: str) -> Optional[str]:
    try:
        resp = requests.get(url, cookies=_OVER18_COOKIES, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.warning(f"[forum_fetcher] 抓取失敗 ({url}): {e}")
        return None


# ── 索引頁解析 ──────────────────────────────────────────────────────────
def _parse_nrec(raw: str) -> Optional[int]:
    """PTT 索引頁 `div.nrec`（推文數概數）不保證是數字：可能是空白（未達門檻）、
    `'爆'`（>=100 推）、或 `'X1'`~`'X9'`／`'XX'`（淨噓，噓數超過推數達到的等級標記）。
    實測 124 篇樣本中 106 筆數字、11 筆「爆」、7 筆空白，樣本沒出現 X 系列但規格仍要求
    能處理，**不可 `int()` 直接轉**（對非數字字串會直接拋 `ValueError` 炸掉整支爬蟲）。

    這個值只是「概數」，真正推噓則數改用文章頁逐則統計（見 `_parse_article_page()`），
    本函式的回傳值不落地存檔，只用來避免解析索引頁時中斷。"""
    raw = raw.strip()
    if not raw:
        return None
    if raw == "爆":
        return 100
    if raw.startswith("X"):
        suffix = raw[1:]
        if suffix == "X":
            return -10
        if suffix.isdigit():
            return -int(suffix)
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _parse_md(date_md: str) -> Optional[tuple]:
    """索引頁日期欄位（`'9/28'`、`' 9/28'`）轉成 `(month, day)`，無年份、解析失敗回 None。"""
    try:
        m, d = (int(x) for x in date_md.replace(" ", "").split("/"))
        return m, d
    except ValueError:
        return None


def _parse_index_page(html: str) -> tuple:
    """解析一頁索引頁，回傳 `(posts, prev_href)`。

    `posts` 為 `[{"href", "title", "author", "date_md", "nrec"}, ...]`；已被刪除的文章
    （索引頁只留下「(本文已被刪除)」文字、`div.title` 內沒有 `<a>`）直接略過，不進
    `posts` 清單。`prev_href` 是「上一頁」（更舊的文章）連結，翻到最舊一頁時為 `None`。
    """
    soup = BeautifulSoup(html, "html.parser")
    posts: List[Dict[str, Any]] = []
    for ent in soup.select("div.r-ent"):
        title_div = ent.find("div", class_="title")
        link = title_div.find("a") if title_div else None
        if link is None:
            continue
        author_div = ent.find("div", class_="author")
        date_div = ent.find("div", class_="date")
        nrec_div = ent.find("div", class_="nrec")
        posts.append({
            "href": link.get("href", ""),
            "title": link.get_text(strip=True),
            "author": author_div.get_text(strip=True) if author_div else None,
            "date_md": date_div.get_text(strip=True) if date_div else "",
            "nrec": _parse_nrec(nrec_div.get_text() if nrec_div else ""),
        })

    prev_href = None
    for a in soup.find_all("a"):
        if "上頁" in a.get_text() and a.get("href"):
            prev_href = a["href"]
            break
    return posts, prev_href


# ── 文章頁解析 ──────────────────────────────────────────────────────────
def _extract_post_key(url_or_href: str) -> Optional[str]:
    """從 PTT 網址抽出穩定去重鍵 `M.xxx.A.xxx`（ADR-P7-05），例如
    `/bbs/Stock/M.1790440627.A.4F7.html` -> `M.1790440627.A.4F7`。"""
    m = _POST_KEY_PATTERN.search(url_or_href)
    return m.group(1) if m else None


def _extract_category(title: str) -> Optional[str]:
    """從標題前綴解析分類（`[標的]`、`[請益]`……），`Re:` 回文形式也要能抓到
    （例如 `Re: [請益] 基本面投資如何驗證自己錯了` -> `請益`）。抓不到回 None。"""
    m = _CATEGORY_PATTERN.match(title.strip())
    return m.group(1) if m else None


def _parse_article_page(html: str) -> Optional[Dict[str, Any]]:
    """解析文章頁：meta（作者／標題／時間）、內文（meta 區塊之後、第一則推文之前）、
    推文逐則依 `推`/`噓`/`→` 分類計數。`main-content` 找不到視為異常頁面（例如文章
    已被站方整篇撤下），回傳 None 由呼叫端略過。"""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find(id="main-content")
    if main is None:
        return None

    meta_values: Dict[str, str] = {}
    for tag_span in main.find_all("span", class_="article-meta-tag"):
        value_span = tag_span.find_next_sibling("span", class_="article-meta-value")
        if value_span is not None:
            meta_values[tag_span.get_text(strip=True)] = value_span.get_text(strip=True)

    title = meta_values.get("標題", "")
    author_raw = meta_values.get("作者", "")
    author = author_raw.split(" ")[0] if author_raw else None

    posted_at = None
    time_raw = meta_values.get("時間")
    if time_raw:
        try:
            posted_at = datetime.strptime(time_raw, _ARTICLE_TIME_FORMAT)
        except ValueError:
            logger.warning(f"[forum_fetcher] 文章時間格式無法解析: {time_raw!r}")

    # 內文：meta 區塊之後、第一個 div.push 之前（規格書明文的解析範圍，含「-- ／發信站／
    # 文章網址」簽名檔區塊——那也是 push 之前的內容，本函式忠實照規格擷取，不額外過濾）。
    body_parts: List[str] = []
    for child in main.children:
        name = getattr(child, "name", None)
        cls = child.get("class") if name else None
        if name == "div" and cls and ("article-metaline" in cls or "article-metaline-right" in cls):
            continue
        if name == "div" and cls and "push" in cls:
            break
        body_parts.append(child.get_text() if name else str(child))
    body = "\n".join(part.strip() for part in body_parts if part and part.strip())

    push_count = boo_count = arrow_count = 0
    for push in main.find_all("div", class_="push"):
        tag_span = push.find("span", class_="push-tag")
        tag = tag_span.get_text(strip=True) if tag_span else ""
        if tag == "推":
            push_count += 1
        elif tag == "噓":
            boo_count += 1
        elif tag == "→":
            arrow_count += 1

    return {
        "title": title,
        "author": author,
        "posted_at": posted_at,
        "body": body,
        "push_count": push_count,
        "boo_count": boo_count,
        "arrow_count": arrow_count,
    }


# ── 股號抽取：code ∪ name 雙路比對 ──────────────────────────────────────
def _build_name_index(symbol_rows: List[Dict[str, Any]]) -> Dict[str, str]:
    """建立「公司名稱 -> 股號」比對表。

    只濾掉長度低於 `MIN_SYMBOL_NAME_LENGTH` 的通用詞雜訊，**不再整批排除「是另一檔標的
    全名子字串」的短名稱**——這是舊版規則（見 git 歷史），已用真實代號主檔實測推翻：

    實測（2026-09-28，`StockRepository.list_symbols_sync("tw")`，台股全代號主檔 2447 檔，
    其中 2412 檔名稱長度達標）：舊規則整批丟棄 100 檔（100/2412 ≈ 4.15%）。全域丟棄比例
    看起來不高，但丟棄的**剛好集中在 PTT 討論度最高的那群股票**：使用者指定的 23 檔熱門股
    裡有 10 檔（43%）整批消失——長榮（子字串於「長榮航」「長榮鋼」「長榮航太」）、台塑
    （「台塑化」）、南亞（「南亞科」）、中鋼（「中鋼特」「中鋼構」）、統一（「統一超」
    「統一證」等一長串 ETF／統一系列基金）、華新（「華新科」）、聯電（「台聯電」）、
    國泰金（「國泰金乙特」）、富邦金（「富邦金乙特」「富邦金丙特」）、台泥（「台泥乙特」）
    ——這些短名稱在 PTT 上幾乎都是被單獨提及（討論母公司本身，而非那些冷門子公司／
    特別股／ETF），舊規則卻讓它們完全抽不到任何標的，等於讓熱門股的召回率全毀。全域
    丟棄率低不代表對真實流量無害，**舊規則不可用**（規格書 §2.2）。

    改採「同一段文字裡最長優先」策略（`_extract_symbols()` 內做）：短名稱一律留在比對
    表裡，只有當「包住它的長名」也同時出現在**同一篇文章**時，才捨棄短名稱的命中結果
    （例如同時出現「長榮」與「長榮航」時只算「長榮航」），短名稱單獨出現時仍正常命中，
    避免砍掉熱門股的召回率，同時保留原本要防的「短名稱其實在講別家公司全名」風險。
    """
    index: Dict[str, str] = {}
    for r in symbol_rows:
        name = r.get("name")
        if not name or len(name) < MIN_SYMBOL_NAME_LENGTH:
            continue
        index[name] = r["symbol"]
    return index


def _extract_symbols(text: str, code_set: set, name_index: Dict[str, str]) -> List[Dict[str, str]]:
    """code ∪ name 雙路比對（規格書「股號抽取」一節）：數字 token 命中已知代號集合走
    `matched_by='code'`；公司名稱命中走 `matched_by='name'`。同一檔標的兩條路徑都命中時
    只留一筆（`replace_post_symbols()` 的複合主鍵 `(post_id, symbol)` 本就不允許重複），
    這裡用 `setdefault` 讓先出現的比對方式（code 優先掃描）保留，供事後稽核比對品質。

    名稱路徑採「同一段文字裡最長優先」：若某名稱是同一篇文章裡另一個也命中的較長名稱的
    真子字串，只採計較長名稱，短名稱的命中捨棄；短名稱單獨出現（沒有更長的命中）時仍
    正常計入。這是取代「整批丟棄短名稱」的防護策略，見 `_build_name_index()` docstring
    的實測數字與決策依據（規格書 §2.2）。"""
    found: Dict[str, str] = {}
    for token in _SYMBOL_CODE_PATTERN.findall(text):
        if token in code_set:
            found.setdefault(token, "code")

    matched_names = [name for name in name_index if name in text]
    for name in matched_names:
        shadowed_by_longer_match = any(
            other != name and name in other for other in matched_names
        )
        if shadowed_by_longer_match:
            continue
        found.setdefault(name_index[name], "name")
    return [{"symbol": sym, "matched_by": mb} for sym, mb in found.items()]


# ── 已知標的／交易日：I/O 邊界（照抄 news_fetcher.py 的既有慣例）─────────────
def _known_symbol_index() -> tuple:
    """回傳 `(code_set, name_index)`，讀取失敗時視為空集合（寧可本次抽不到任何標的，
    也不要因為 DB 暫時打不通就讓整支爬蟲中斷——比照 news_fetcher.py `_known_tw_symbols()`
    的既有容錯慣例）。"""
    try:
        rows = StockRepository().list_symbols_sync(market_type="tw")
    except Exception as e:
        logger.warning(f"[forum_fetcher] 讀取 symbols 失敗，本次視為空集合: {e}")
        return set(), {}
    code_set = {r["symbol"] for r in rows}
    name_index = _build_name_index(rows)
    return code_set, name_index


def _is_trading_day_checker(market_type: str = "tw"):
    """比照 services/news_fetcher.py `_is_trading_day_checker()` 的既有寫法，組出
    `effective_trade_date()` 需要的 `is_trading_day` callable。"""
    try:
        holidays = StockRepository().get_no_trading_days_sync(market_type)
    except Exception as e:
        logger.warning(f"[forum_fetcher] 讀取 market_no_trading_days 失敗，暫以純週末判斷: {e}")
        holidays = set()
    return is_weekday_trading_day(holidays)


# ── 索引頁往前翻頁，收集目標日期候選文章 ─────────────────────────────────
def _collect_target_date_articles(target_date: date, max_pages: int = 8) -> List[Dict[str, Any]]:
    """從 PTT Stock 板索引頁往前翻頁，收集 `target_date` 當天可能發文的文章。

    索引頁日期只有 `M/D`、無年份（規格書明文：不可拿它算 `effective_trade_date`），這裡
    只拿來做兩件事：①粗篩「這篇文章值得抓文章頁確認」；②決定翻頁翻到哪裡可以停止
    （比照既有 `services/news_fetcher.py` `fetch_ptt_stock()` 的既有慣例：同一頁由舊到新
    排列，`posts[0]`（頁面第一篇）代表本頁最舊的一篇，若已早於目標日期，不必再往前翻）。
    真正落地的 `posted_at`／`effective_trade_date` 一律用文章頁的真實時間戳計算。"""
    target_md = (target_date.month, target_date.day)
    candidates: List[Dict[str, Any]] = []
    url = _INDEX_URL
    for _ in range(max_pages):
        html = _fetch_html(url)
        if html is None:
            break
        _save_raw_snapshot("index", html)
        posts, prev_href = _parse_index_page(html)

        for post in posts:
            if _parse_md(post["date_md"]) == target_md:
                candidates.append(post)

        oldest_md = _parse_md(posts[0]["date_md"]) if posts else None
        if oldest_md and oldest_md < target_md:
            break  # 本頁最舊的一篇已早於目標日，不需要再往前翻頁
        if not prev_href:
            break
        url = f"{_BASE_URL}{prev_href}"
        _throttle()
    return candidates


def _strip_ptt_signature_lines(body: str) -> str:
    """剝除 PTT 站方自動附加、對情緒分析毫無價值的簽名檔行（`※ 發信站:`／`※ 文章網址:`／
    `※ 編輯:`）。這些行落在 `_parse_article_page()` 既定的擷取範圍內（meta 之後、第一則
    推文之前），本函式不改那個擷取範圍、只在拿到 body 之後事後過濾行，並且**必須在
    `MAX_BODY_CHARS` 截斷之前**呼叫——否則短文會被這幾行站方樣板佔掉大半截斷額度。"""
    lines = [
        line for line in body.split("\n")
        if not line.strip().startswith(_SIGNATURE_LINE_PREFIXES)
    ]
    return "\n".join(lines).strip()


def _fetch_and_build_post(
    href: str, *, code_set: set, name_index: Dict[str, str], is_trading_day,
) -> Optional[Dict[str, Any]]:
    """抓單篇文章頁並組出可直接交給 `ForumRepository.upsert_post()` 的欄位字典。
    抓取或解析失敗（例如文章被撤下）回傳 None，由呼叫端略過該篇、不中斷整批。"""
    url = href if href.startswith("http") else f"{_BASE_URL}{href}"
    post_key = _extract_post_key(url)
    if post_key is None:
        logger.warning(f"[forum_fetcher] 無法從網址解析 post_key，略過: {url}")
        return None

    html = _fetch_html(url)
    if html is None:
        return None
    _save_raw_snapshot(post_key, html)

    parsed = _parse_article_page(html)
    if parsed is None or parsed["posted_at"] is None:
        logger.warning(f"[forum_fetcher] 文章頁解析失敗或缺少時間戳，略過: {url}")
        return None

    title = parsed["title"]
    body = _strip_ptt_signature_lines(parsed["body"]) if parsed["body"] else parsed["body"]
    symbols = _extract_symbols(f"{title}\n{body}", code_set, name_index)

    category = _extract_category(title)
    author = parsed["author"]

    return {
        "source": "ptt_stock",
        "post_key": post_key,
        "url": url,
        "title": title,
        "category": category[:MAX_CATEGORY_CHARS] if category else None,
        "author": author[:MAX_AUTHOR_CHARS] if author else None,
        "body_excerpt": body[:MAX_BODY_CHARS] if body else None,
        "push_count": parsed["push_count"],
        "boo_count": parsed["boo_count"],
        "arrow_count": parsed["arrow_count"],
        "posted_at": parsed["posted_at"],
        "effective_trade_date": effective_trade_date(parsed["posted_at"], is_trading_day),
        "symbols": symbols,
    }


# ── 落地：寫入 Postgres（run_async 橋接，見 repositories/forum_repository.py）───────
async def _persist_posts_async(posts: List[Dict[str, Any]]) -> Dict[str, int]:
    """單一背景 session 一次寫完整批，比照 news_fetcher.py `_write_news_batch_async()`
    的既有慣例（一批一個 transaction，呼叫端統一 commit）。抽不到任何標的的文章仍會呼叫
    `upsert_post()` 落地（它本身仍是有效的討論資料），只是不呼叫 `replace_post_symbols()`。

    每篇文章的寫入包在 `session.begin_nested()`（SAVEPOINT）裡，比照
    `repositories/news_repository.py` `insert_news_if_new()` 的既有先例：單篇寫入失敗
    （例如少數超長欄位仍溢位、或其他未預期的 DB 例外）只記 warning、rollback 到該篇的
    SAVEPOINT 後略過，session 其餘部分不受影響、仍可繼續處理下一篇——不能讓單篇失敗
    拖垮整批（整天）的抓取結果。"""
    posts_written = 0
    posts_failed = 0
    symbol_links_written = 0
    async with get_background_session() as session:
        repo = ForumRepository(session)
        for post in posts:
            try:
                async with session.begin_nested():
                    post_id = await repo.upsert_post(
                        source=post["source"], post_key=post["post_key"], url=post["url"],
                        title=post["title"], category=post["category"], author=post["author"],
                        body_excerpt=post["body_excerpt"], push_count=post["push_count"],
                        boo_count=post["boo_count"], arrow_count=post["arrow_count"],
                        posted_at=post["posted_at"], effective_trade_date=post["effective_trade_date"],
                    )
                    if post["symbols"]:
                        await repo.replace_post_symbols(post_id, post["symbols"])
            except Exception as e:
                posts_failed += 1
                logger.warning(
                    f"[forum_fetcher] 單篇貼文落地失敗，略過（post_key={post.get('post_key')}）: {e}"
                )
                continue
            posts_written += 1
            if post["symbols"]:
                symbol_links_written += len(post["symbols"])
        await session.commit()
    return {
        "posts_written": posts_written,
        "symbol_links_written": symbol_links_written,
        "posts_failed": posts_failed,
    }


# ── 對外主流程（供未來 API 端點／排程呼叫，本片尚未接線）───────────────────
def run_forum_fetch(trigger_type: str = "manual", target_date: Optional[date] = None) -> Dict[str, Any]:
    """一次完整的 PTT Stock 板抓取：索引頁翻頁 -> 逐篇文章頁 -> 股號比對 -> 落地。

    與 `services/fetcher.py` 系列既有慣例一致：單一 `fetch_status` 單例保證同時只有一輪
    在跑。本片不含 LLM 評分、不註冊排程、不開 API 端點（見規格書 §6 路線圖，皆為後續切片）。
    """
    target_date = target_date or date.today()
    fetch_status.start(f"開始抓取 PTT Stock 板（{target_date.isoformat()}）...")
    try:
        code_set, name_index = _known_symbol_index()
        is_trading_day = _is_trading_day_checker("tw")

        fetch_status.update(1, 3, "翻頁收集目標日期候選文章...")
        candidates = _collect_target_date_articles(target_date)

        fetch_status.update(2, 3, f"抓取 {len(candidates)} 篇文章內文與推文...")
        posts: List[Dict[str, Any]] = []
        for i, candidate in enumerate(candidates):
            post = _fetch_and_build_post(
                candidate["href"], code_set=code_set, name_index=name_index,
                is_trading_day=is_trading_day,
            )
            if post is not None:
                posts.append(post)
            if i < len(candidates) - 1:
                _throttle()

        fetch_status.update(3, 3, f"寫入 {len(posts)} 篇貼文...")
        write_result = run_async(_persist_posts_async(posts)) if posts else {
            "posts_written": 0, "symbol_links_written": 0, "posts_failed": 0,
        }

        failed_suffix = (
            f"，落地失敗 {write_result['posts_failed']} 篇" if write_result["posts_failed"] else ""
        )
        fetch_status.complete(
            f"完成：候選 {len(candidates)} 篇，成功解析並寫入 {write_result['posts_written']} 篇"
            f"{failed_suffix}，標的關聯 {write_result['symbol_links_written']} 筆"
        )
        return {
            "trigger_type": trigger_type,
            "target_date": target_date.isoformat(),
            "candidates_found": len(candidates),
            "posts_written": write_result["posts_written"],
            "posts_failed": write_result["posts_failed"],
            "symbol_links_written": write_result["symbol_links_written"],
        }
    except Exception as e:
        logger.error(f"[forum_fetcher] 抓取失敗: {e}")
        fetch_status.fail(str(e))
        raise
