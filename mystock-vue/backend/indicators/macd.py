"""MACD 指標計算（Phase1-基礎量化與技術面 設計文件 FR-P1-2）。

只負責「算數值」，不碰任何策略判斷邏輯 —— 策略層只能使用這裡算好的結果，不可自己再算
MACD 或加減乘除（策略管理架構 設計文件第 9 節鐵則）。
"""
from typing import List, Optional, Tuple

from indicators.moving_average import ema

Series = List[Optional[float]]


def macd(
    closes: Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> Tuple[Series, Series, Series]:
    """回傳 (dif, signal, histogram)。

    DIF = EMA(fast_period) − EMA(slow_period)；signal = EMA(DIF, signal_period)；
    histogram = DIF − signal。內部一律呼叫 indicators.moving_average.ema()，不另寫一份
    （FR-P1-2）。

    收盤價 0（代表當天沒回補到行情）在此清成 None 才餵給 ema()；DIF／histogram 之後不再
    重複清理——這兩者是相減後的結果，可能真的等於 0（代表無趨勢差），不是缺值。
    """
    n = len(closes)
    if n == 0:
        return [], [], []

    cleaned = [c if c else None for c in closes]
    ema_fast = ema(cleaned, fast_period)
    ema_slow = ema(cleaned, slow_period)

    dif: Series = [None] * n
    for i in range(n):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            dif[i] = round(ema_fast[i] - ema_slow[i], 4)

    signal = ema(dif, signal_period)

    histogram: Series = [None] * n
    for i in range(n):
        if dif[i] is not None and signal[i] is not None:
            histogram[i] = round(dif[i] - signal[i], 4)

    return dif, signal, histogram
