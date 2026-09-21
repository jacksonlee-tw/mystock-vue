"""
ai/rule_alignment.py
FR-5.6（Phase5-三層式 AI 決策引擎與戰情室.md）：AI 研判與規則引擎當日訊號的比對，只標示、不仲裁
（見該文件「為何只標示、不仲裁」）。手動診股（ai_analysis.py）與批次（ai/batch_job.py）共用同一個
判定函式，確保兩條路徑的「一致／分歧」語意完全一致。

刻意不重新查詢 alert_repository／DB：直接複用 build_quant_summary() 已經組好、原樣存進
quant_summary 快照的 summary["recent_alerts"]（ADR-AI-15：輸出即快照），零額外 I/O。
"""
from __future__ import annotations
from datetime import date
from typing import Any, Optional

_BULLISH_SIGNAL_TYPES = {"BUY"}
_BEARISH_SIGNAL_TYPES = {"SELL"}


def compute_alignment(
    verdict: str, recent_alerts: list[dict[str, Any]] | None, trade_date: date,
) -> Optional[str]:
    """回傳 'aligned'／'diverged'；查無當日規則訊號或 verdict 為 neutral 時回傳 None
    （無從比較，不得強行貼標籤）。"""
    if verdict == "neutral" or not recent_alerts:
        return None

    trade_date_str = trade_date.isoformat()
    today_signal_types = {
        a.get("signal_type") for a in recent_alerts if a.get("trade_date") == trade_date_str
    }
    if not today_signal_types:
        return None

    if verdict == "bullish" and today_signal_types & _BULLISH_SIGNAL_TYPES:
        return "aligned"
    if verdict == "bearish" and today_signal_types & _BEARISH_SIGNAL_TYPES:
        return "aligned"
    if (verdict == "bullish" and today_signal_types & _BEARISH_SIGNAL_TYPES) or (
        verdict == "bearish" and today_signal_types & _BULLISH_SIGNAL_TYPES
    ):
        return "diverged"
    return None
