"""方向 → 多空分類/訊號類型的對照（均線策略警示系統 設計文件第 6.3 節 by_direction 統計、
策略管理架構 設計文件 ALERT_EVENT.signal_type 欄位）。集中一處，scanner 與 API 都用同一份對照，
避免兩邊各自猜測方向字串代表多方還是空方。
"""

_BULLISH_PREFIXES = (
    "cross_above",
    "golden_cross",
    "bullish_alignment",
    "squeeze_breakout",
    "oversold",
    "pullback_support",
    "bottom_turnover",
    "short_squeeze",
    "kd_golden_cross",  # KD 超賣區黃金交叉（KD指標 設計規格書 §5.5，P2 背離上線時補 kd_bullish_divergence）
)
_BEARISH_PREFIXES = (
    "cross_under",
    "death_cross",
    "bearish_alignment",
    "overbought",
    "distribution_top",
    "revenue_yoy_decline",
    # KD 死亡交叉刻意顯式登記——classify_direction() 預設回傳 bullish，"kd_" 前綴不會被
    # 上面既有的 "death_cross" 比對到（direction 字串是 kd_death_cross_overbought，不是
    # death_cross_xxx），漏登記會讓死亡交叉被誤判成 BUY 而不會報錯（KD指標 設計規格書 §5.5）。
    "kd_death_cross",
)


def classify_direction(direction: str) -> str:
    """回傳 'bullish' 或 'bearish'。"""
    if any(direction.startswith(p) for p in _BEARISH_PREFIXES):
        return "bearish"
    return "bullish"


def to_signal_type(direction: str) -> str:
    """回傳 'BUY' 或 'SELL'（對齊策略管理架構 設計文件 ALERT_EVENT.signal_type）。"""
    return "SELL" if classify_direction(direction) == "bearish" else "BUY"
