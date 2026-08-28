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


def ema(values: Series, period: int) -> Series:
    """指數移動平均，MACD 等遞迴型指標的前置基礎（Phase1-基礎量化與技術面 設計文件 FR-P1-1）。

    起始種子：累積滿 period 筆有效值後取簡單平均作為種子，之後才開始遞迴
    （EMA_t = alpha * v_t + (1-alpha) * EMA_{t-1}，alpha = 2/(period+1)）。

    缺值處理與 stochastic.py 的既有決策一致（缺值不重置遞迴狀態）：遇到 None 時該點輸出
    None，但遞迴值（prev）原樣保留，等下一筆有效值出現時直接沿用它繼續平滑，避免復牌／
    補資料後在原本沒有交叉的地方製造假交叉。

    比照 sma()：本函式只把 None 視為缺值，是否把 0 也當缺值由呼叫端在傳入前自行清理
    （見 services/stock_service.py 既有的 `r.get("close") or None` 慣例）——因為 ema() 同時
    被 macd() 用來對 DIF（可能真的等於 0）做訊號線平滑，函式本身不能把 0 當缺值處理。
    """
    n = len(values)
    out: Series = [None] * n
    if n == 0 or period <= 0:
        return out

    alpha = 2.0 / (period + 1)
    seed_sum = 0.0
    seed_count = 0
    prev: Optional[float] = None

    for i, v in enumerate(values):
        if prev is None:
            if v is None:
                continue
            seed_sum += v
            seed_count += 1
            if seed_count == period:
                prev = seed_sum / period
                out[i] = round(prev, 4)
            continue
        if v is None:
            continue
        prev = alpha * v + (1 - alpha) * prev
        out[i] = round(prev, 4)
    return out
