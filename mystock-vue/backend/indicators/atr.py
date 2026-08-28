"""ATR 平均真實區間計算（Phase1-基礎量化與技術面 設計文件 FR-P1-5）。

只負責「算數值」，不碰任何策略判斷邏輯（策略管理架構 設計文件第 9 節鐵則）。

TR 的 Wilder 1/period 遞迴平滑，與 stochastic.py／rsi.py 選擇 Wilder 平滑的理由一致
（ADR-KD-01）。本階段只交付數值，是否用於停損位階計算見該設計文件 §9 Q-4（不在此決定）。
"""
from typing import List, Optional

Series = List[Optional[float]]


def _clean(value: Optional[float]) -> Optional[float]:
    """0 代表當天沒回補到行情，一律視為缺值（比照 indicators/stochastic.py 的 _clean()）。"""
    if value is None or value == 0:
        return None
    return float(value)


def atr(highs: Series, lows: Series, closes: Series, period: int = 14) -> Series:
    """回傳與輸入等長的 ATR 序列；序列首日必為 None（無前一日收盤價可算 TR）。

    TR_t = max(H_t − L_t, |H_t − C_{t-1}|, |L_t − C_{t-1}|)
    ATR 為 TR 的 Wilder 遞迴平滑：ATR_t = (ATR_{t-1} * (period-1) + TR_t) / period
    起始種子：前 period 筆 TR 的簡單平均。

    缺值處理與 stochastic.py／rsi.py 一致：任一輸入缺值時該點 TR 為 None、該點輸出 None，
    但遞迴狀態（ATR 前值、上一筆有效收盤價）保留不重置，等資料恢復後直接沿用繼續平滑。
    """
    n = len(closes)
    out: Series = [None] * n
    if n == 0 or period <= 0:
        return out

    highs_c = [_clean(v) for v in highs]
    lows_c = [_clean(v) for v in lows]
    closes_c = [_clean(v) for v in closes]

    prev_close: Optional[float] = None
    prev_atr: Optional[float] = None
    seed_trs: List[float] = []

    for i in range(n):
        h, l, c = highs_c[i], lows_c[i], closes_c[i]
        if h is None or l is None or c is None or prev_close is None:
            if c is not None:
                prev_close = c
            continue

        tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
        prev_close = c

        if prev_atr is None:
            seed_trs.append(tr)
            if len(seed_trs) == period:
                prev_atr = sum(seed_trs) / period
                out[i] = round(prev_atr, 4)
            continue

        prev_atr = (prev_atr * (period - 1) + tr) / period
        out[i] = round(prev_atr, 4)

    return out
