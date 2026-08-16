"""KD 隨機指標 (Stochastic Oscillator) 計算（KD指標 設計規格書 第 3 節）。

只負責「算數值」，不碰任何策略判斷邏輯 —— 策略層（strategies/conditions_tech.py）只能使用
這裡算好的結果，不可自己再算 KD 或加減乘除（策略管理架構 設計文件第 9 節鐵則）。

刻意不使用 TA-Lib：其 STOCH 函數不論哪種 matype 都無法重現台股慣例「平滑係數固定 1/3」的
遞迴平滑，算出來的數字會跟國內看盤軟體對不起來（見 KD指標 設計規格書 ADR-KD-01）。
"""
import logging
from typing import Dict, List, Optional, Tuple

Series = List[Optional[float]]

logger = logging.getLogger("mystock-backend")

# 目前只實作台股慣例（決議 D1：台股與美股一體適用，見 KD指標 設計規格書 §12 D1）。
# "sma"（歐美慣例）保留字，尚未實作。
_SUPPORTED_SMOOTHING = {"wilder_1_3"}
_warned_unsupported_smoothing: set = set()


def _clean(value: Optional[float]) -> Optional[float]:
    """0 代表當天沒回補到行情，一律視為缺值（比照 services/chip_provider.py 的 _clean()）。"""
    if value is None or value == 0:
        return None
    return float(value)


def stochastic(
    highs: Series,
    lows: Series,
    closes: Series,
    fastk_period: int = 9,
    slowk_period: int = 3,
    slowd_period: int = 3,
    seed: float = 50.0,
    warmup_bars: int = 25,
    smoothing: str = "wilder_1_3",
) -> Tuple[Series, Series]:
    """回傳 (k_series, d_series)，長度與輸入相同；未達可信賴條件的位置為 None。

    台股慣例遞迴平滑（KD指標 設計規格書 §3.2）：
        RSV_t = (C_t − LLV(L, n)_t) / (HHV(H, n)_t − LLV(L, n)_t) × 100
        K_t   = (2/3) × K_{t−1} + (1/3) × RSV_t
        D_t   = (2/3) × D_{t−1} + (1/3) × K_t
    slowk_period / slowd_period 在此代表平滑係數 1/period（3 → 1/3），不是簡單移動平均天數。

    邊界條件（KD指標 設計規格書 §3.2 表格，全部在此處理，呼叫端不需另行防呆）：
    - High/Low/Close 為 0 或 None 一律視為缺值。
    - 視窗內任一根缺值：該根 RSV 為 None，但遞迴狀態（前一組 K/D）保留不重置，避免復牌／
      補資料後在原本沒有交叉的地方製造假交叉。
    - HHV == LLV（區間內高低同價，如連續一價漲停跌停）：RSV 視為 50（中性），不算缺值。
    - 序列開頭不足 fastk_period 根、或尚未累積滿 warmup_bars 次有效遞迴：輸出 None
      （暖身期推導見 KD指標 設計規格書 §3.3，種子誤差以 (2/3)^n 衰減）。
    """
    if smoothing not in _SUPPORTED_SMOOTHING:
        if smoothing not in _warned_unsupported_smoothing:
            logger.warning(f"[KD] 不支援的平滑方式 {smoothing!r}，已退回 wilder_1_3 繼續計算")
            _warned_unsupported_smoothing.add(smoothing)
        smoothing = "wilder_1_3"

    n = len(closes)
    k_out: Series = [None] * n
    d_out: Series = [None] * n
    if n == 0 or fastk_period <= 0:
        return k_out, d_out

    highs_c = [_clean(v) for v in highs]
    lows_c = [_clean(v) for v in lows]
    closes_c = [_clean(v) for v in closes]

    k_alpha = 1.0 / slowk_period
    d_alpha = 1.0 / slowd_period

    k_prev: Optional[float] = None
    d_prev: Optional[float] = None
    warm_count = 0  # 已成功算出 RSV 並完成一次遞迴平滑的次數（缺值的天不計入，暖身天然順延）

    for i in range(n):
        if i < fastk_period - 1:
            continue

        window_h = highs_c[i - fastk_period + 1: i + 1]
        window_l = lows_c[i - fastk_period + 1: i + 1]
        c = closes_c[i]

        if c is None or any(v is None for v in window_h) or any(v is None for v in window_l):
            continue  # 遞迴狀態（k_prev/d_prev）刻意不重置，見上方 docstring

        hhv = max(window_h)
        llv = min(window_l)
        rsv = 50.0 if hhv == llv else (c - llv) / (hhv - llv) * 100

        k_seed = k_prev if k_prev is not None else seed
        d_seed = d_prev if d_prev is not None else seed
        k_now = k_alpha * rsv + (1 - k_alpha) * k_seed
        d_now = d_alpha * k_now + (1 - d_alpha) * d_seed

        k_prev, d_prev = k_now, d_now
        warm_count += 1

        if warm_count >= warmup_bars:
            k_out[i] = round(k_now, 4)
            d_out[i] = round(d_now, 4)

    return k_out, d_out


def compute_kd_set(
    highs: Series,
    lows: Series,
    closes: Series,
    param_sets: List[Tuple[int, int, int]],
    warmup_bars: int = 25,
    smoothing: str = "wilder_1_3",
) -> Dict[Tuple[int, int, int], Tuple[Series, Series]]:
    """回傳 {(fastk_period, slowk_period, slowd_period): (k_series, d_series)}。

    對應 ScanContext.kd 的資料形狀（KD指標 設計規格書 §4.1），風格比照
    moving_average.py 的 compute_ma_set()：多組參數各自獨立計算，互不影響。
    """
    return {
        tuple(params): stochastic(
            highs, lows, closes, *params, warmup_bars=warmup_bars, smoothing=smoothing
        )
        for params in param_sets
    }
