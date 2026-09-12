"""
services/news_fetcher.py
新聞／PTT 討論度抓取（docs/16.AI技術分析/Phase4-輕量化新聞輿情與總經監控.md §3）。

比照 services/fetcher.py 的 fetch_status 單例與節流設計；資料來源白名單見
services/news_config.py（news_sources.yaml）。

兩段式落地（ADR-P4-04）：
  ① JSON 緩衝檔 `data/_news/raw/{source_id}/*.json`（原始回應快照，供第二階段失敗時重跑，
     不需要重新對外部來源發請求——外部新聞列表 API 只給最近 N 則，過期即抓不回來）
  ② 解析寫入 PostgreSQL `stock_news`／`stock_discussion_buzz`（經 repositories/news_repository.py
     的 run_async() 橋接，因為本模組是同步爬蟲，比照 fetcher.py／mops_fetcher.py 的既有慣例）

僅支援 TW（Phase4 文件 §1.3）：cnyes 回應裡的美股代號（如 'US-TSM'）與非本站追蹤的台股
代號一律跳過，不寫入 stock_news。

情緒評分（L1/L2）留待 P2（Spike-0 選型結果出爐後）才實作；本模組寫入的 `sentiment_score`/
`sentiment_label`/`sentiment_engine` 目前一律為 NULL，符合 schema 允許缺值的設計。
"""
import json
import logging
import os
import random
import re
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import requests

from config import DATA_DIR
from indicators.news_time import (
    effective_trade_date,
    is_weekday_trading_day,
    normalize_title,
    percentile_rank_of,
    simhash,
    title_hash,
)
from repositories.news_repository import NewsRepository, get_background_session, run_async
from repositories.stock_repository import StockRepository
from services.fetcher import FetchStatusManager
from services.news_config import NewsSourcesConfig, load_news_sources_config
from services.news_dedup import resolve_l3_duplicate

logger = logging.getLogger("mystock-backend")

fetch_status = FetchStatusManager()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

_NEWS_RAW_DIR = os.path.join(DATA_DIR, "_news", "raw")
_TW_SYMBOL_PATTERN = re.compile(r"^\d{4,6}[A-Z]?$")
_SYMBOL_TOKEN_PATTERN = re.compile(r"\d{4,6}[A-Z]?")


def _throttle(rate_limit_seconds: List[float]) -> None:
    lo_hi = (list(rate_limit_seconds) + [3, 5])[:2]
    time.sleep(random.uniform(lo_hi[0], lo_hi[1]))


def _save_raw_snapshot(source_id: str, payload: Any) -> Optional[str]:
    """§3.2 兩段式落地的第一階段：原始回應先落地成 JSON，第二階段（寫 Postgres）失敗時
    可依此重跑，不必重新對外部來源發請求。"""
    try:
        day_dir = os.path.join(_NEWS_RAW_DIR, source_id)
        os.makedirs(day_dir, exist_ok=True)
        path = os.path.join(day_dir, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, default=str)
        return path
    except Exception as e:
        logger.warning(f"[news_fetcher] 原始快照落地失敗 ({source_id}): {e}")
        return None


def _known_tw_symbols() -> set:
    try:
        rows = StockRepository().list_symbols_sync(market_type="tw")
        return {r["symbol"] for r in rows}
    except Exception as e:
        logger.warning(f"[news_fetcher] 讀取 symbols 失敗，本次視為空集合（不會誤存美股代號）: {e}")
        return set()


def _is_trading_day_checker(market_type: str = "tw"):
    try:
        holidays = StockRepository().get_no_trading_days_sync(market_type)
    except Exception as e:
        logger.warning(f"[news_fetcher] 讀取 market_no_trading_days 失敗，暫以純週末判斷: {e}")
        holidays = set()
    return is_weekday_trading_day(holidays)


# ── cnyes（鉅亨網台股新聞）──────────────────────────────────────────────
def fetch_cnyes(config: NewsSourcesConfig, known_symbols: set, is_trading_day, pages: int = 3) -> List[Dict[str, Any]]:
    source = config.get("cnyes")
    if not source or not source.enabled:
        return []
    endpoint = source.endpoint or "https://api.cnyes.com/media/api/v1/newslist/category/tw_stock_news"

    raw_pages: List[dict] = []
    news_items: List[Dict[str, Any]] = []
    for page in range(1, pages + 1):
        try:
            resp = requests.get(endpoint, params={"page": page, "limit": 30}, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            body = resp.json()
        except Exception as e:
            logger.warning(f"[news_fetcher] cnyes 第 {page} 頁抓取失敗: {e}")
            break
        raw_pages.append(body)
        data = ((body.get("items") or {}).get("data")) or []
        if not data:
            break
        for item in data:
            symbols = [
                s for s in (item.get("stock") or [])
                if _TW_SYMBOL_PATTERN.match(s) and s in known_symbols
            ]
            if not symbols:
                continue
            title = item.get("title", "").strip()
            if not title:
                continue
            published_at = datetime.fromtimestamp(item["publishAt"])
            news_url = f"https://news.cnyes.com/news/id/{item['newsId']}"
            eff_date = effective_trade_date(published_at, is_trading_day)
            for sym in symbols:
                news_items.append({
                    "symbol": sym,
                    "source": "cnyes",
                    "title": title,
                    "news_url": news_url,
                    "published_at": published_at,
                    "effective_trade_date": eff_date,
                })
        _throttle(source.rate_limit_seconds)

    if raw_pages:
        _save_raw_snapshot("cnyes", raw_pages)
    return news_items


# ── yahoo_stock（預設關閉，§2：關閉來源完全不抓取）─────────────────────────
def fetch_yahoo_stock(config: NewsSourcesConfig, known_symbols: set, is_trading_day) -> List[Dict[str, Any]]:
    source = config.get("yahoo_stock")
    if not source or not source.enabled:
        return []
    if not source.endpoint:
        logger.warning("[news_fetcher] yahoo_stock 已啟用但 endpoint 尚未設定（見 Phase4 文件 §15.4），本次略過")
        return []
    logger.info("[news_fetcher] yahoo_stock 抓取邏輯尚未實作，本次略過（預設 enabled=false，非常規路徑）")
    return []


# ── PTT Stock 板（kind='buzz'，只計討論量）─────────────────────────────────
_PTT_TITLE_PATTERN = re.compile(r'<div class="title">\s*(.*?)</div>', re.S)
_PTT_DATE_PATTERN = re.compile(r'<div class="date">\s*([^<]*)</div>')
_PTT_LINK_PATTERN = re.compile(r'<a[^>]*>(.*?)</a>', re.S)
_PTT_PREV_PAGE_PATTERN = re.compile(r'href="(/bbs/Stock/index(\d+)\.html)">&lsaquo; 上頁')


def _parse_ptt_page(html: str) -> tuple[list[tuple[str, Optional[str]]], Optional[str]]:
    """回傳 `[(date_md, title_or_None), ...]`（`title` 為 None 代表該篇已被刪除，PTT
    索引頁只留下「(本文已被刪除)」文字、沒有 `<a>` 連結）與上一頁的完整 href。"""
    titles = _PTT_TITLE_PATTERN.findall(html)
    dates = _PTT_DATE_PATTERN.findall(html)
    posts = []
    for title_html, date_md in zip(titles, dates):
        link = _PTT_LINK_PATTERN.search(title_html)
        posts.append((date_md.strip(), link.group(1).strip() if link else None))
    prev = _PTT_PREV_PAGE_PATTERN.search(html)
    return posts, (prev.group(1) if prev else None)


def _parse_md(date_md: str) -> Optional[tuple[int, int]]:
    try:
        m, d = (int(x) for x in date_md.replace(" ", "").split("/"))
        return m, d
    except ValueError:
        return None


def fetch_ptt_stock(
    config: NewsSourcesConfig, known_symbols: set, target_date: date, max_pages: int = 8,
) -> Dict[str, int]:
    """回傳 `{symbol: post_count}`：`target_date` 當天，PTT Stock 板標題含對應代號的討論篇數。

    已知限制（輕量化統計，非精確逐篇歸戶，見 Phase4 文件 §15.3-3）：PTT 索引頁日期只有
    「M/D」無年份、由舊到新排列，且換日時同一頁可能橫跨兩天；標題含代號才計入，未提及
    任何已知代號的討論串不會被算進任何一檔。"""
    source = config.get("ptt_stock")
    if not source or not source.enabled:
        return {}
    endpoint = source.endpoint or "https://www.ptt.cc/bbs/Stock/index.html"
    target_md = (target_date.month, target_date.day)

    counts: Dict[str, int] = {}
    url = endpoint
    for _ in range(max_pages):
        try:
            resp = requests.get(url, cookies={"over18": "1"}, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"[news_fetcher] PTT 抓取失敗 ({url}): {e}")
            break

        posts, prev_href = _parse_ptt_page(resp.text)
        _save_raw_snapshot("ptt_stock", {"url": url, "post_count_on_page": len(posts)})

        for date_md, title in posts:
            parsed = _parse_md(date_md)
            if parsed != target_md or title is None:
                continue
            for token in _SYMBOL_TOKEN_PATTERN.findall(title):
                if token in known_symbols:
                    counts[token] = counts.get(token, 0) + 1

        oldest = _parse_md(posts[0][0]) if posts else None
        if oldest and oldest < target_md:
            break  # 整頁最舊日期已早於目標日，不需要再往前翻頁
        if not prev_href:
            break
        url = f"https://www.ptt.cc{prev_href}"
        _throttle(source.rate_limit_seconds)

    return counts


# ── 兩段式落地：寫入 Postgres（run_async 橋接，見 repositories/news_repository.py）─────
async def _write_news_batch_async(items: List[Dict[str, Any]], config: NewsSourcesConfig) -> Dict[str, int]:
    inserted, skipped = 0, 0
    async with get_background_session() as session:
        repo = NewsRepository(session)
        for item in items:
            normalized = normalize_title(item["title"])
            row = {
                "symbol": item["symbol"],
                "market_type": "tw",
                "source": item["source"],
                "title": item["title"],
                "news_url": item["news_url"],
                "published_at": item["published_at"],
                "effective_trade_date": item["effective_trade_date"],
                "title_hash": title_hash(normalized),
                "simhash": simhash(normalized),
                "extra_meta": {},
            }
            news_id = await repo.insert_news_if_new(row)
            if news_id is None:
                skipped += 1
                continue
            inserted += 1
            await resolve_l3_duplicate(
                repo,
                news_id=news_id,
                symbol=row["symbol"],
                source_id=row["source"],
                simhash_value=row["simhash"],
                published_at=row["published_at"],
                config=config,
            )
        await session.commit()
    return {"inserted": inserted, "skipped": skipped}


async def _write_buzz_async(symbol_counts: Dict[str, int], trade_date: date, source_id: str) -> int:
    written = 0
    async with get_background_session() as session:
        repo = NewsRepository(session)
        for symbol, count in symbol_counts.items():
            history = await repo.get_buzz_history(symbol=symbol, source=source_id, window=249)
            history_values = [float(h["post_count"]) for h in history] + [float(count)]
            percentile = percentile_rank_of(history_values, float(count))
            await repo.upsert_buzz(
                symbol=symbol, market_type="tw", trade_date=trade_date,
                source=source_id, post_count=count, percentile_rank=percentile,
            )
            written += 1
        await session.commit()
    return written


# ── 對外主流程（供 API 端點與（未來）排程呼叫）──────────────────────────────
def run_news_fetch(trigger_type: str = "manual") -> Dict[str, Any]:
    """一次完整的新聞＋PTT 討論度抓取。與 fetcher.py 系列既有慣例一致：
    单一 `fetch_status` 單例保證同時只有一輪在跑，執行中重複觸發直接被 API 層擋下。"""
    fetch_status.start("開始抓取新聞與 PTT 討論度...")
    try:
        config = load_news_sources_config()
        known_symbols = _known_tw_symbols()
        is_trading_day = _is_trading_day_checker("tw")
        today = date.today()

        fetch_status.update(1, 4, "抓取 cnyes 新聞...")
        news_items = fetch_cnyes(config, known_symbols, is_trading_day)
        news_items += fetch_yahoo_stock(config, known_symbols, is_trading_day)

        fetch_status.update(2, 4, f"寫入 {len(news_items)} 筆新聞候選...")
        write_result = run_async(_write_news_batch_async(news_items, config)) if news_items else {"inserted": 0, "skipped": 0}

        fetch_status.update(3, 4, "抓取 PTT 討論量...")
        ptt_counts = fetch_ptt_stock(config, known_symbols, today)
        buzz_written = run_async(_write_buzz_async(ptt_counts, today, "ptt_stock")) if ptt_counts else 0

        fetch_status.complete(
            f"完成：新聞候選 {len(news_items)} 筆（新增 {write_result['inserted']}、"
            f"去重跳過 {write_result['skipped']}），PTT 討論度 {buzz_written} 檔"
        )
        return {
            "news_candidates": len(news_items),
            "news_inserted": write_result["inserted"],
            "news_skipped_as_duplicate": write_result["skipped"],
            "buzz_symbols_written": buzz_written,
            "trigger_type": trigger_type,
        }
    except Exception as e:
        logger.error(f"[news_fetcher] 抓取失敗: {e}")
        fetch_status.fail(str(e))
        raise
