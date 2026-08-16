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
    "kd_golden_cross",  # KD 超賣區黃金交叉（KD指標 設計規格書 §5.5）
    "pick_",            # 選股買進訊號（選股功能與爬蟲 規格書 §13）
)
_BEARISH_PREFIXES = (
    "cross_under",
    "death_cross",
    "bearish_alignment",
    "overbought",
    "distribution_top",
    "revenue_yoy_decline",
    "kd_death_cross",
    "exit_",            # 出場風控賣出訊號（選股功能與爬蟲 規格書 §13）
)


def classify_direction(direction: str) -> str:
    """回傳 'bullish' 或 'bearish'。"""
    if any(direction.startswith(p) for p in _BEARISH_PREFIXES):
        return "bearish"
    return "bullish"


def to_signal_type(direction: str) -> str:
    """回傳 'BUY' 或 'SELL'（對齊策略管理架構 設計文件 ALERT_EVENT.signal_type）。"""
    return "SELL" if classify_direction(direction) == "bearish" else "BUY"
