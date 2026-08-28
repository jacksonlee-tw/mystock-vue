"""近 N 日高低點（支撐／壓力）計算（Phase1-基礎量化與技術面 設計文件 FR-P1-6）。

只負責「算數值」，不碰任何策略判斷邏輯（策略管理架構 設計文件第 9 節鐵則）。

取代 ai/summary.py 先前對顯示區間直接取 max/min 的 inline 邏輯（該版視窗等於使用者選的
月份數、且無法在指標庫外重用）；第二個消費者是《進出場策略規劃》§4.2 移動停利的
lookback_high。
"""
from typing import List, Optional, Tuple

Series = List[Optional[float]]


def _clean(value: Optional[float]) -> Optional[float]:
    """0 代表當天沒回補到行情，一律視為缺值（比照 indicators/stochastic.py 的 _clean()）。"""
    if value is None or value == 0:
        return None
    return float(value)


def rolling_high_low(highs: Series, lows: Series, window: int) -> Tuple[Series, Series]:
    """回傳 (resistance, support)：固定視窗（如 20／60 日）內出現過的最高／最低價。

    視窗內只要有 1 天有效值即可算出（不像 SMA 要求整窗都有效）——高低點本來就是「近 N 日
    內出現過的極值」，資料不足時取現有天數內的極值即可，不需要像均線一樣整窗缺一天就
    整段斷線；只有視窗內完全沒有任何有效值時才輸出 None。
    """
    n = len(highs)
    resistance: Series = [None] * n
    support: Series = [None] * n
    if n == 0 or window <= 0:
        return resistance, support

    highs_c = [_clean(v) for v in highs]
    lows_c = [_clean(v) for v in lows]

    for i in range(n):
        start = max(0, i - window + 1)
        window_h = [v for v in highs_c[start:i + 1] if v is not None]
        window_l = [v for v in lows_c[start:i + 1] if v is not None]
        if window_h:
            resistance[i] = round(max(window_h), 4)
        if window_l:
            support[i] = round(min(window_l), 4)

    return resistance, support
