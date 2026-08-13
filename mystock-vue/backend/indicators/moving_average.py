"""均線相關指標計算（均線策略警示系統 設計文件第 5.1 / 6.1 節）。

只負責「算數值」，不碰任何策略判斷邏輯 —— 策略層（strategies/conditions_tech.py）
只能使用這裡算好的結果，不可自己再算均線或加減乘除（策略管理架構 設計文件第 9 節鐵則）。
"""
from typing import List, Optional

Series = List[Optional[float]]


def sma(values: Series, window: int) -> Series:
    """簡單移動平均。窗口內只要有任一天是 None（缺值），該點就留空，不補零。

    演算法對齊 frontend/src/utils/movingAverage.js 的 sma()，確保前後端算出的均線一致
    （均線策略警示系統 設計文件第 6.1 節「設計決策」）。
    """
    out: Series = [None] * len(values)
    total = 0.0
    valid_count = 0
    for i, v in enumerate(values):
        if v is not None:
            total += v
            valid_count += 1
        if i >= window:
            old = values[i - window]
            if old is not None:
                total -= old
                valid_count -= 1
        if i >= window - 1 and valid_count == window:
            out[i] = round(total / window, 4)
    return out


def bias_series(closes: Series, ma_values: Series) -> Series:
    """乖離率 BIAS = (收盤價 - MA) / MA * 100（均線策略警示系統 設計文件第 2.4 節）。"""
    out: Series = [None] * len(closes)
    for i, (close, ma) in enumerate(zip(closes, ma_values)):
        if close is None or ma is None or ma == 0:
            continue
        out[i] = round((close - ma) / ma * 100, 4)
    return out


def compute_ma_set(closes: Series, periods: List[int]) -> dict:
    """回傳 {"MA5": [...], "MA20": [...], ...}（均線策略警示系統 設計文件第 6.1 節 API 契約）。"""
    return {f"MA{p}": sma(closes, p) for p in periods}
