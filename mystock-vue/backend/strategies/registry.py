"""Condition Registry（策略管理架構 設計文件第 2 節 / 程式清單）。

策略條件抽象為獨立函數，透過 @condition 裝飾器動態註冊，掃描器（scanner.py）核心碼
不需要因為新增一種條件類型而修改。目前只註冊 conditions_tech.py 的均線條件；
未來 conditions_chip.py / conditions_risk.py / conditions_fund.py 依同樣方式掛進來即可。
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

ConditionFunc = Callable[[Any, int, dict], Optional[dict]]


@dataclass
class ConditionSpec:
    type: str
    min_bars: int
    func: ConditionFunc


CONDITION_REGISTRY: Dict[str, ConditionSpec] = {}


def condition(type: str, min_bars: int = 2):
    """註冊一個條件函式。min_bars 是最起碼要有幾根 K 棒才「有機會」判斷（實際上大天期 MA
    是否足夠仍由 indicators.moving_average.sma() 回傳 None 把關，見設計文件第 9 節）。"""

    def decorator(func: ConditionFunc) -> ConditionFunc:
        CONDITION_REGISTRY[type] = ConditionSpec(type=type, min_bars=min_bars, func=func)
        return func

    return decorator
