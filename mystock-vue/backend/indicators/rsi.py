"""RSI 相對強弱指標計算（Phase1-基礎量化與技術面 設計文件 FR-P1-3）。

只負責「算數值」，不碰任何策略判斷邏輯（策略管理架構 設計文件第 9 節鐵則）。

採 Wilder 遞迴平滑（1/period）而非簡單移動平均版——與 stochastic.py 選擇台股慣例遞迴
平滑的理由相同（ADR-KD-01：避免與國內看盤軟體對不起來）。超買／超賣門檻不進此函式，
由呼叫端判讀（Phase1-基礎量化與技術面 設計文件 §5）。
"""
from typing import List, Optional

Series = List[Optional[float]]


def _clean(value: Optional[float]) -> Optional[float]:
    """0 代表當天沒回補到行情，一律視為缺值（比照 indicators/stochastic.py 的 _clean()）。"""
    if value is None or value == 0:
        return None
    return float(value)


def rsi(closes: Series, period: int = 14) -> Series:
    """回傳與輸入等長的 RSI 序列（0～100）；暖身期未滿或缺值的位置為 None。

    Wilder 遞迴平滑：
        avg_gain_t = (avg_gain_{t-1} * (period-1) + gain_t) / period
        avg_loss_t = (avg_loss_{t-1} * (period-1) + loss_t) / period
        RS = avg_gain / avg_loss；RSI = 100 − 100 / (1 + RS)
    起始種子：前 period 筆漲跌幅的簡單平均。

    缺值處理與 stochastic.py 一致：收盤價缺值時無法算出當天漲跌幅，該點輸出 None，
    但遞迴狀態（avg_gain/avg_loss）保留不重置，等資料恢復後直接沿用繼續平滑。

    連續同值（漲跌幅全為 0）時 avg_gain 與 avg_loss 皆為 0，比照 stochastic.py 對
    HHV==LLV 的處理，視為中性 50，不得除以零；只有 avg_loss 為 0（連續上漲）視為 100，
    只有 avg_gain 為 0（連續下跌）視為 0。
    """
    n = len(closes)
    out: Series = [None] * n
    if n == 0 or period <= 0:
        return out

    cleaned = [_clean(c) for c in closes]

    avg_gain: Optional[float] = None
    avg_loss: Optional[float] = None
    seed_gains: List[float] = []
    seed_losses: List[float] = []
    prev_close: Optional[float] = None

    for i in range(n):
        c = cleaned[i]
        if c is None or prev_close is None:
            prev_close = c
            continue

        change = c - prev_close
        gain = change if change > 0 else 0.0
        loss = -change if change < 0 else 0.0
        prev_close = c

        if avg_gain is None:
            seed_gains.append(gain)
            seed_losses.append(loss)
            if len(seed_gains) == period:
                avg_gain = sum(seed_gains) / period
                avg_loss = sum(seed_losses) / period
            else:
                continue
        else:
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_gain == 0 and avg_loss == 0:
            out[i] = 50.0
        elif avg_loss == 0:
            out[i] = 100.0
        elif avg_gain == 0:
            out[i] = 0.0
        else:
            rs = avg_gain / avg_loss
            out[i] = round(100 - 100 / (1 + rs), 4)

    return out
