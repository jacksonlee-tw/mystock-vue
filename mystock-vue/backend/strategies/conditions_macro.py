"""大盤總經全域鎖閘門條件（docs/16.AI技術分析/Phase4-輕量化新聞輿情與總經監控.md §5.2、§6.1，
ADR-P4-06）。

**與 `strategies/conditions_sentiment.py` 同一用法（v2.8 更新）**：掛進策略設定的 `gates:`
清單才會真的發揮閘門效果，見該檔頭說明，不重複贅述。

`market_trend` 參數目前支援 `"above_20ma"`／`"above_60ma"`，對應讀取 `ctx.macro_flags`
裡 `f"{ctx.market}_above_20ma"`／`f"{ctx.market}_above_60ma"` 這兩個鍵（見
`services/macro_analytics.py` 的 `get_macro_flags()` 說明）。§5.2 原文另外提到「總經指標
同向轉緊（例如 10 年期殖利率短期急升）」，但原文只是舉例、沒有給出具體判定門檻（漲幅多少
算「急升」、回看幾天），規格書 §15.4 也沒有補上這個落差——這裡刻意不猜一個門檻數字，避免
用臆測的業務規則誤導使用者，等之後有明確規則再補上對應旗標與這裡的判斷分支。
"""
from typing import List, Optional

from services.chip_provider import ScanContext
from strategies.registry import condition

_SUPPORTED_TRENDS = ("above_20ma", "above_60ma")


def _eval_macro_filter(ctx: ScanContext, idx: int, params: dict) -> Optional[dict]:
    """大盤環境判斷：讀 `ctx.macro_flags`（單次掃描共用的市場層級旗標，不逐日重算、
    也不在此重新查詢）。成立回傳 details，否則回傳 None（比照 `conditions_pick.py`
    `_eval_valuation_filter()` 的既有慣例）。"""
    market_trend = params.get("market_trend")
    if market_trend not in _SUPPORTED_TRENDS:
        return None
    if not ctx.macro_flags:
        return None

    flag_key = f"{ctx.market}_{market_trend}"
    if ctx.macro_flags.get(flag_key) is not True:
        return None

    return {"market_trend": market_trend, "flag_key": flag_key}


@condition(type="macro_filter", min_bars=1, requires=("macro_flags",))
def macro_filter(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """大盤總經環境閘門條件（§5.2／§6.1）。掛進策略的 `gates:` 清單才會真的擋掉主觸發
    訊號，見檔頭說明。"""
    details = _eval_macro_filter(ctx, idx, params)
    if details is None:
        return []
    return [{"direction": "macro_gate_pass", "details": details}]
