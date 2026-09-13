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
from typing import Callable, Iterable, Optional

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


def simhash(normalized_title: str, bits: int = 63) -> int:
    """SimHash：對每個 shingle 雜湊後依每個 bit 是否為 1 做加權累計，最後對每個維度取正負號
    決定該 bit 的最終值。**刻意用 63 bit、不是教科書常見的 64 bit**：`stock_news.simhash`
    欄位是 Postgres 有號 `BIGINT`（範圍 -2^63 ～ 2^63-1），完整 64-bit 雜湊值有一半機率落在
    2^63 ～ 2^64-1 之間、寫入時直接觸發 `asyncpg.exceptions.DataError`（實測撞過一次真實
    標題就出現：`9298988751881561404 (value out of int64 range)`）。63 bit 的雜湊空間
    （約 92 京種取值）對「近似標題比對」這種用途仍綽綽有餘，換掉一個 bit 不影響鑑別度，
    比起改 schema 或在讀寫兩端另外做二補數轉換簡單得多，不需要新增 migration。"""
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


# ── §4.3 個股情緒動能與 Buzz Surge（P2）───────────────────────────────────
def recent_trading_dates(upto_date: date, window: int, is_trading_day: Callable[[date], bool]) -> list[date]:
    """回傳「含 `upto_date`」往前數 `window` 個交易日的日期清單（由舊到新）。純函式，
    交易日判定沿用 `is_weekday_trading_day()` 注入的 callable，不重複實作交易日邏輯。
    供 `services/news_sentiment.py` 組出明確日期清單，交給
    `NewsRepository.get_news_count_by_dates()` 補零查詢（見該方法 docstring：純
    `GROUP BY` 會漏掉零則新聞的交易日，讓平均值虛高）。"""
    dates: list[date] = []
    cursor = upto_date
    while len(dates) < window:
        if is_trading_day(cursor):
            dates.append(cursor)
        cursor -= timedelta(days=1)
    return list(reversed(dates))


def weighted_sentiment_avg(scored_rows: list[dict], source_weights: dict[str, float]) -> Optional[float]:
    """`sentiment_5d = Σ(weight_source × score_i) / Σ(weight_source)`（§4.3）。
    `scored_rows` 為 `[{"source": str, "sentiment_score": float}, ...]`
    （`NewsRepository.get_recent_scores()` 的回傳形狀），找不到權重的來源預設 1.0，
    避免單一來源設定缺漏就讓整檔股票的 sentiment_5d 直接算不出來。"""
    if not scored_rows:
        return None
    total_weight = 0.0
    weighted_sum = 0.0
    for row in scored_rows:
        weight = source_weights.get(row["source"], 1.0)
        score = row.get("sentiment_score")
        if score is None:
            continue
        weighted_sum += weight * float(score)
        total_weight += weight
    if total_weight <= 0:
        return None
    return weighted_sum / total_weight


def buzz_surge_ratio(today_count: int, history_counts: list[int]) -> Optional[float]:
    """`Buzz Surge = 當日新聞則數 / 近 20 交易日平均則數`（§4.3，新聞曝光倍數；
    與 §4.4 PTT 討論量分位數是兩套不同指標，此處算的是新聞則數本身的暴增倍率）。
    `history_counts` 不含當日，歷史平均為 0（例如剛上市或近期完全零新聞）時無意義，
    回傳 None 由呼叫端自行決定顯示方式，不得除以 0 也不得虛報一個假倍數。"""
    if not history_counts:
        return None
    avg = sum(history_counts) / len(history_counts)
    if avg <= 0:
        return None
    return today_count / avg


DivergenceFlag = Optional[str]  # "BULLISH_STALL" | "BEARISH_RESILIENT" | None


def divergence_flag(
    sentiment_5d: Optional[float], price_change_pct: Optional[float],
    *, threshold: float = 0.3,
) -> DivergenceFlag:
    """§4.3 背離標記：結合既有 `ScanContext` 的價格序列（由呼叫端傳入 `price_change_pct`，
    本函式對資料庫／ScanContext 零依賴，保持與 indicators/ 目錄其餘函式一致的純函式風格）。

    - **利多鈍化 BULLISH_STALL**：`sentiment_5d >= threshold` 但股價未漲（`price_change_pct <= 0`）
    - **利空不跌 BEARISH_RESILIENT**：`sentiment_5d <= -threshold` 但股價未跌（`price_change_pct >= 0`）

    只是訊號的補充註記，不單獨成為訊號（§4.3 明文）——實際掛進 `ScanContext` 並在
    `strategies/scanner.py` 迴圈中呼叫屬於 P4 範疇（見規格書 §15.2 P4 列），本函式只負責
    判斷邏輯本身，方便 P4 直接呼叫、也方便獨立單元測試。"""
    if sentiment_5d is None or price_change_pct is None:
        return None
    if sentiment_5d >= threshold and price_change_pct <= 0:
        return "BULLISH_STALL"
    if sentiment_5d <= -threshold and price_change_pct >= 0:
        return "BEARISH_RESILIENT"
    return None


def sentiment_5d_series(
    trading_dates: list[str], scored_rows: list[dict], source_weights: dict[str, float], window: int = 5,
) -> list[Optional[float]]:
    """`ScanContext.sentiment_5d`（P4 §6.2）：對齊 `trading_dates`（`ChipDataProvider.get_bars()`
    已組好的該股實際交易日清單，由舊到新）的逐日 5 日加權情緒分數序列。

    刻意用「回看視窗＝`trading_dates` 本身往前數 `window` 個索引」而非另外查交易日曆——
    `trading_dates` 已經是這檔股票真實有交易的日子（沒交易就不會有 K 棒、不會出現在這個清單
    裡），用它自己的索引往前數就是正確的「近 N 個交易日」定義，不需要再靠
    `is_weekday_trading_day()` 重建一次交易日曆（那是給「這檔股票完全沒有資料的日子」用的
    情境，例如新股上市前，此處不適用）。

    `scored_rows`：`NewsRepository.get_recent_scores()` 的回傳形狀
    `[{"source", "sentiment_score", "effective_trade_date"}, ...]`，一次查詢涵蓋整個
    `trading_dates` 範圍（呼叫端負責），這裡只在記憶體裡逐日分桶，不再查詢資料庫。"""
    if not trading_dates:
        return []
    # 依 effective_trade_date（ISO 字串）分桶，同一天可能有多筆
    by_date: dict[str, list[dict]] = {}
    for row in scored_rows:
        d = row.get("effective_trade_date")
        d_str = d.isoformat() if hasattr(d, "isoformat") else str(d)
        by_date.setdefault(d_str, []).append(row)

    series: list[Optional[float]] = []
    for i in range(len(trading_dates)):
        window_dates = trading_dates[max(0, i - window + 1): i + 1]
        window_rows = [row for d_str in window_dates for row in by_date.get(d_str, [])]
        series.append(weighted_sentiment_avg(window_rows, source_weights))
    return series
