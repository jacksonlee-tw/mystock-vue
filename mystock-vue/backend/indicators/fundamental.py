"""基本面時間與可見性衍生工具（選股功能與爬蟲 規格書 §4.1、§5.3）。"""
from datetime import date
from typing import Any


def revenue_visible_from(month_key: str) -> date:
    """月營收 "YYYY-MM" 在哪一天起視為市場已公開可用。"""
    year, month = (int(part) for part in month_key.split("-"))
    if month == 12:
        year, month = year + 1, 1
    else:
        month += 1
    return date(year, month, 11)


def latest_visible_month(revenue_dict: dict[str, Any], as_of: date) -> str | None:
    """回傳 as_of 這天已經公開、最新一個月的 "YYYY-MM"；無已公開月份則回傳 None。"""
    visible = [m for m in revenue_dict if revenue_visible_from(m) <= as_of]
    return max(visible) if visible else None


def eps_visible_from(year_quarter: str) -> date:
    """季報 "YYYY-Qn" 在法定申報截止日當天起視為市場已公開可用。"""
    year_text, quarter_text = year_quarter.split("-Q", 1)
    year, quarter = int(year_text), int(quarter_text)
    deadlines = {
        1: (year, 5, 15),
        2: (year, 8, 14),
        3: (year, 11, 14),
        4: (year + 1, 3, 31),
    }
    try:
        return date(*deadlines[quarter])
    except KeyError as exc:
        raise ValueError(f"不合法的季別：{year_quarter}") from exc


def latest_visible_quarter(quarterly_dict: dict[str, Any], as_of: date) -> str | None:
    """回傳 as_of 當日依申報時點可使用的最新季報；無資料時回傳 None。"""
    visible = [quarter for quarter in quarterly_dict if eps_visible_from(quarter) <= as_of]
    return max(visible) if visible else None
