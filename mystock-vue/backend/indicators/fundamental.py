"""基本面時間與可見性衍生工具（選股功能與爬蟲 規格書 §4.1、§5.3）。"""
from datetime import date
from typing import Any, Dict, List, Optional


def revenue_visible_from(month_key: str) -> date:
    """月營收 "YYYY-MM" 在哪一天起視為市場已公開可用。"""
    year, month = (int(part) for part in month_key.split("-"))
    if month == 12:
        year, month = year + 1, 1
    else:
        month += 1
    return date(year, month, 11)


def latest_visible_month(revenue_dict: Dict[str, Any], as_of: date) -> Optional[str]:
    """回傳 as_of 這天已經公開、最新一個月的 "YYYY-MM"；無已公開月份則回傳 None。"""
    visible = [m for m in revenue_dict if revenue_visible_from(m) <= as_of]
    return max(visible) if visible else None
