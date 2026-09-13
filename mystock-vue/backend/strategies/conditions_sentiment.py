"""新聞情緒閘門條件（docs/16.AI技術分析/Phase4-輕量化新聞輿情與總經監控.md §4.1、§6.1，
ADR-P4-06）。

`sentiment_filter` 語意上是「情緒未達門檻不進場」的**閘門**，不是 `strategies/filters.py`
那種「只加分、不擋」的濾網（ADR-P4-06 明訂兩者分工，型別名稱刻意沿用 `sentiment_filter`
避免與 filters 模組混淆——見該 ADR 說明）。

**重要限制（P4 開工前已與使用者確認，刻意不動 scanner.py）**：`strategies/scanner.py` 目前
的 condition 評估迴圈沒有「多個 condition AND 在一起才算一次訊號」的機制——`conditions:`
清單裡每一項各自獨立評估、各自獨立產生候選警示（OR 關係，各自用自己的 `direction` 去重）。
核對現有 24 條策略設定檔，目前一條都沒有掛超過 1 個 condition，證實這條 AND 語意路徑從未
被使用過。也就是說：**把本檔的 `sentiment_filter` 掛在某個策略的 `conditions:` 清單裡，
目前不會真的擋掉同策略下其他 condition 的訊號**，只會變成一個獨立發自己警示的條件類型。
要真正達成「情緒不過關就擋掉主訊號」的效果，需要先擴充 scanner.py（例如新增策略層級的
`gates:` 欄位，或比照 `conditions_pick.py` 的 `stock_pick_resonance` 用 `_eval_*`
私有函式做 AND 組合、另外設計一個複合 condition），這是後續待辦，不在本次 P4 範圍內
（見規格書 §15.2 P4 列的補充說明）。

本檔的 `_eval_sentiment_filter()` 私有函式即是比照 `conditions_pick.py` 的既有慣例——先把
可重用的判斷邏輯寫好，供未來真的要做 AND 組合時直接呼叫，不必重寫一次。
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
    """情緒面閘門條件（§4.1／§6.1）。**目前技術上等同獨立 condition**，見檔頭說明——
    scanner.py 尚未支援 condition 間的 AND 組合，掛在任何策略上都不會真的擋掉其他訊號。"""
    details = _eval_sentiment_filter(ctx, idx, params)
    if details is None:
        return []
    return [{"direction": "sentiment_gate_pass", "details": details}]
