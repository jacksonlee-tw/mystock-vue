"""新聞 point-in-time 對齊與標題去重的純函式工具（docs/16.AI技術分析/
Phase4-輕量化新聞輿情與總經監控.md §3.3、§3.4，ADR-P4-02、ADR-P4-05）。

比照 indicators/fundamental.py 的既有慣例：這裡只放不碰資料庫、不發請求的純函式，
交易日曆／候選比對範圍等外部輸入一律由呼叫端（services/news_fetcher.py）注入，
維持 indicators/ 目錄「純函式，方便單元測試」的既有分工。
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime, time as time_cls, timedelta
from typing import Callable, Iterable

# ── §3.4 Point-in-time 對齊：effective_trade_date（ADR-P4-05）─────────────
_MARKET_CLOSE_CUTOFF = time_cls(13, 30)


def effective_trade_date(published_at: datetime, is_trading_day: Callable[[date], bool]) -> date:
    """新聞的可見時點對齊交易日：

    - `published_at` 落在交易日且時刻 <= 13:30（台股收盤）→ 當日即為 effective_trade_date。
    - 晚於 13:30，或 `published_at` 當天本身不是交易日 → 順延至下一個交易日。

    `is_trading_day` 由呼叫端注入（通常是「非週末 AND 不在 market_no_trading_days 內」），
    保持本函式對資料庫零依賴、可直接單元測試（比照 latest_visible_month() 的既有寫法）。
    """
    d = published_at.date()
    if published_at.time() <= _MARKET_CLOSE_CUTOFF and is_trading_day(d):
        return d
    candidate = d + timedelta(days=1)
    while not is_trading_day(candidate):
        candidate += timedelta(days=1)
    return candidate


def is_weekday_trading_day(no_trading_days: Iterable[date]) -> Callable[[date], bool]:
    """組出一個 `is_trading_day` callable：週一～五 AND 不在已知非交易日集合內。

    `market_no_trading_days` 只收錄「曾經探測過」的非交易日（見 db/models.py 的
    MarketNoTradingDay 註解），對尚未探測到的未來假日會失準，但這與既有 backfill.py
    面對同一張表的既有限制一致，不是本模組獨有的缺口。
    """
    holidays = set(no_trading_days)

    def _check(d: date) -> bool:
        return d.weekday() < 5 and d not in holidays

    return _check


# ── §3.3 L2 去重：標題正規化與雜湊 ─────────────────────────────────────
_SOURCE_PREFIX_PATTERN = re.compile(
    r"^[〈<［\[]?(財經|即時|快訊|盤中速報|盤後速報|熱門股|焦點股|國際)[〉>］\]]?\s*"
)
_PUNCTUATION_PATTERN = re.compile(r"[\s　，。！？、,.!?;:；：\"'「」『』（）()\-—_]+")


def normalize_title(title: str) -> str:
    """全形轉半形、去除來源前綴標記、移除空白與標點、統一大小寫（§3.3）。"""
    if not title:
        return ""
    # 全形轉半形（NFKC 正規化涵蓋大多數全形符號/字母/數字）
    normalized = unicodedata.normalize("NFKC", title)
    normalized = _SOURCE_PREFIX_PATTERN.sub("", normalized)
    normalized = _PUNCTUATION_PATTERN.sub("", normalized)
    return normalized.strip().lower()


def title_hash(normalized_title: str) -> str:
    """正規化標題的 SHA-256（L2 去重鍵，對應 stock_news.title_hash）。"""
    return hashlib.sha256(normalized_title.encode("utf-8")).hexdigest()


# ── §3.3 L3 去重：SimHash 近似比對 ─────────────────────────────────────
def _shingles(normalized_title: str, n: int = 2) -> list[str]:
    """中文標題無天然詞界，且專案「非必要不新增重依賴」（CLAUDE.md §2.4 精神，見
    Phase3 文件同一結論），不引入分詞套件，改用字元 n-gram（bigram）當作 token，
    是 CJK 文本做 SimHash / 相似度比對的常見輕量做法。"""
    if len(normalized_title) < n:
        return [normalized_title] if normalized_title else []
    return [normalized_title[i:i + n] for i in range(len(normalized_title) - n + 1)]


def simhash(normalized_title: str, bits: int = 64) -> int:
    """64-bit SimHash：對每個 shingle 雜湊後依每個 bit 是否為 1 做加權累計，
    最後對每個維度取正負號決定該 bit 的最終值。"""
    tokens = _shingles(normalized_title)
    if not tokens:
        return 0
    weights = [0] * bits
    for token in tokens:
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        for i in range(bits):
            weights[i] += 1 if (h >> i) & 1 else -1
    fingerprint = 0
    for i in range(bits):
        if weights[i] > 0:
            fingerprint |= (1 << i)
    return fingerprint


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def is_near_duplicate(hash_a: int, hash_b: int, max_distance: int) -> bool:
    return hamming_distance(hash_a, hash_b) <= max_distance


# ── §4.4 PTT 過熱分位數：今日值在近 N 日分佈中的排名 ─────────────────────
def percentile_rank_of(history_values: list[float], today_value: float) -> float:
    """回傳 `today_value` 在 `history_values`（含今日自身）分佈中的排名（0.0～1.0）：
    「今天的討論量比過去這段期間裡幾成的日子都高」。

    **刻意不重用 indicators/chip.py 的 `rolling_percentile()`**：那個函式回答的是相反方向
    的問題——「給定一個百分位 P，對應的數值是多少」（例如「券資比近60日第90百分位的數值」，
    做為門檻使用）；本函式要的是「給定一個數值，它落在第幾百分位」，兩者互為逆運算，
    硬套會算出錯的語意（見 Phase4 文件 §15.4 對此落差的說明）。演算法本身仍是同一套
    排序＋線性內插精神，只是方向相反：
    `rank = (小於等於 today_value 的筆數 - 1 + 介於相鄰筆之間的內插比例) / (總筆數 - 1)`。
    """
    if not history_values:
        return 0.0
    values = sorted(history_values)
    n = len(values)
    if n == 1:
        return 1.0
    # 找出 today_value 在排序後陣列中的插入位置，並在相同數值的區間內線性內插
    import bisect

    lo = bisect.bisect_left(values, today_value)
    hi = bisect.bisect_right(values, today_value)
    if lo == hi:
        # today_value 不在陣列中不會發生（history_values 含今日自身），保底處理
        rank_pos = lo
    else:
        rank_pos = (lo + hi - 1) / 2
    return max(0.0, min(1.0, rank_pos / (n - 1)))
