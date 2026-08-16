"""Condition Registry（策略管理架構 設計文件第 2 節 / 程式清單）。

策略條件抽象為獨立函數，透過 @condition 裝飾器動態註冊，掃描器（scanner.py）核心碼
不需要因為新增一種條件類型而修改。目前只註冊 conditions_tech.py 的均線條件；
未來 conditions_chip.py / conditions_risk.py / conditions_fund.py 依同樣方式掛進來即可。
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

ConditionFunc = Callable[[Any, int, dict], Optional[dict]]


@dataclass
class ConditionSpec:
    type: str
    min_bars: int
    func: ConditionFunc
    # ScanContext 上必須非空的欄位（例如 "kd"），供 scanner.py 做「強制資料預檢」
    # （策略管理架構 設計文件第 9 節鐵則；KD指標 設計規格書 §5.1 補上此欄位前 requires 一直不存在）。
    # 只檢查「欄位存不存在／是否為空」，欄位內某組參數是否存在由條件函式自己判斷。
    requires: Tuple[str, ...] = field(default_factory=tuple)


CONDITION_REGISTRY: Dict[str, ConditionSpec] = {}


def condition(type: str, min_bars: int = 2, requires: Tuple[str, ...] = ()):
    """註冊一個條件函式。

    min_bars：scanner.py 逐標的判斷 ctx.length 是否達標，不足者整個條件略過該標的
    （KD指標 設計規格書 §5.1 之前 scanner.py 從未讀取此欄位，僅各條件函式自行 `if idx < N`
    防呆；本次起 scanner.py 一併檢查，各條件內既有的自我防護仍保留，屬雙重保險）。
    requires：ScanContext 上要有值的欄位名稱，例如 ("kd",)。
    """

    def decorator(func: ConditionFunc) -> ConditionFunc:
        CONDITION_REGISTRY[type] = ConditionSpec(type=type, min_bars=min_bars, func=func, requires=requires)
        return func

    return decorator
