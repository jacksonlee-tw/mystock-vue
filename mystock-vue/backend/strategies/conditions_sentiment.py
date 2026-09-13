"""新聞情緒閘門條件（docs/16.AI技術分析/Phase4-輕量化新聞輿情與總經監控.md §4.1、§6.1，
ADR-P4-06）。

`sentiment_filter` 語意上是「情緒未達門檻不進場」的**閘門**，不是 `strategies/filters.py`
那種「只加分、不擋」的濾網（ADR-P4-06 明訂兩者分工，型別名稱刻意沿用 `sentiment_filter`
避免與 filters 模組混淆——見該 ADR 說明）。

**用法（v2.8 更新）**：掛進策略設定的 `gates:` 清單（不是 `conditions:`）才會真的發揮閘門
效果——`strategies/scanner.py` 的 `_evaluate_gates()` 會在主觸發 condition 成立時，
逐一評估 `gates:` 裡的每個型別，全部通過（回傳非空）才放行該筆候選警示。掛在
`conditions:` 裡仍然可以動（會變成一個獨立發自己警示的條件類型），但不會有「擋掉別的
訊號」的效果——`strategies/config_loader.py` 的 YAML 載入批次會在這種誤用情境下記警告。

本檔的 `_eval_sentiment_filter()` 私有函式比照 `conditions_pick.py` 的既有慣例，把
可重用的判斷邏輯與 `@condition` 註冊薄殼分離。
"""
from typing import List, Optional

from services.chip_provider import ScanContext
from strategies.registry import condition


def _eval_sentiment_filter(ctx: ScanContext, idx: int, params: dict) -> Optional[dict]:
    """情緒面判斷：5 日加權情緒分數上下限、PTT 討論量過熱上限。成立回傳 details，
    否則回傳 None（比照 `conditions_pick.py` `_eval_valuation_filter()` 的既有慣例）。

    §1.3 明訂本階段僅支援 TW，非台股一律不成立；`ctx.sentiment_5d` 為空（呼叫端
    `get_bars()` 未帶 `with_sentiment=True`，或該股尚無任何評分資料）時同樣不成立，
    不得以 0 或猜測值代入。"""
    if ctx.market != "tw" or not ctx.sentiment_5d:
        return None

    score = ctx.sentiment_5d[idx]
    if score is None:
        return None

    min_score = params.get("min_score")
    max_score = params.get("max_score")
    if min_score is not None and score < min_score:
        return None
    if max_score is not None and score > max_score:
        return None

    max_buzz_percentile = params.get("max_buzz_percentile")
    buzz = ctx.buzz_percentile[idx] if ctx.buzz_percentile else None
    if max_buzz_percentile is not None and buzz is not None and buzz > max_buzz_percentile:
        # §15.3-1 設計啟示：PTT 過熱的散戶討論量視為反向雜訊，寧可保守放行不足
        # 也不要誤判——放行的意思是「這裡判不通過」，讓上層不產生訊號。
        return None

    return {
        "sentiment_5d": score,
        "buzz_percentile": buzz,
        "news_count": ctx.news_count[idx] if ctx.news_count else None,
    }


@condition(type="sentiment_filter", min_bars=1, requires=("sentiment_5d",))
def sentiment_filter(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """情緒面閘門條件（§4.1／§6.1）。掛進策略的 `gates:` 清單才會真的擋掉主觸發訊號，
    見檔頭說明；回傳值本身跟一般 condition 同一種形狀，方便直接借用既有評估邏輯。"""
    details = _eval_sentiment_filter(ctx, idx, params)
    if details is None:
        return []
    return [{"direction": "sentiment_gate_pass", "details": details}]
