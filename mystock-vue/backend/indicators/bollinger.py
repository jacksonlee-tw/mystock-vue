"""布林通道計算（Phase1-基礎量化與技術面 設計文件 FR-P1-4）。

只負責「算數值」，不碰任何策略判斷邏輯（策略管理架構 設計文件第 9 節鐵則）。
"""
import statistics
from typing import List, Optional, Tuple

from indicators.moving_average import sma

Series = List[Optional[float]]


def bollinger_bands(
    closes: Series,
    period: int = 20,
    num_std: float = 2.0,
    middle: Optional[Series] = None,
) -> Tuple[Series, Series, Series, Series]:
    """回傳 (upper, middle, lower, bandwidth)。

    中軌就是 SMA(period)——若呼叫端已經算好對應天期的均線（比照 compute_ma_set() 的既有
    結果），應直接以 middle 參數傳入，不要讓這裡重算一次（ADR-P1-05：避免同資料算兩次、
    浮點結果分歧）；未傳入時才在此呼叫 sma() 現算。

    bandwidth = (upper − lower) / middle，middle 為 0 或 None 時該點為 None。
    視窗內任一天缺值（None）或資料不足一整個視窗，該點維持 None，比照 sma() 的既有規則
    （截斷後計算，資料不足只會誠實斷線，見 ADR-P1-04）。標準差為 0（連續同價）時
    upper=middle=lower、bandwidth=0，不得拋除以零例外。
    """
    n = len(closes)
    mid = middle if middle is not None else sma(closes, period)

    upper: Series = [None] * n
    lower: Series = [None] * n
    bandwidth: Series = [None] * n

    for i in range(n):
        if i >= len(mid) or mid[i] is None:
            continue
        window = closes[i - period + 1: i + 1]
        if len(window) < period or any(v is None for v in window):
            continue
        std = statistics.pstdev(window)
        upper[i] = round(mid[i] + num_std * std, 4)
        lower[i] = round(mid[i] - num_std * std, 4)
        if mid[i]:
            bandwidth[i] = round((upper[i] - lower[i]) / mid[i], 4)

    return upper, mid, lower, bandwidth
