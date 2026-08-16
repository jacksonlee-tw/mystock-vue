"""賣股策略 設計文件第四節「基本面惡化策略」§1「成長動能衰竭」的實作。

只做「連續 N 個月營收 YoY 轉負」這一條——文件四-2「估值過高均值回歸」需要 P/E 資料源
（尚未建置，見 docs/5.籌碼選股策略/籌碼選股.md 來源 J），本檔案不涉及。

沿用 conditions_tech.py / conditions_chip.py 的慣例：函式簽章 (ctx, idx, params) -> List[dict]，
只讀 ctx.revenue（services/chip_provider.py 已讀好的 MOPS 月營收），不在這裡發任何請求或讀檔。

**Point-in-time 對齊**：月營收公告日與交易日曆是兩套獨立時間軸，必須先換算「這個月的營收
資料在哪一個交易日之後才算公開」，否則會用未來才公布的數字去判斷過去的交易日（look-ahead
bias）。MOPS 規定次月 10 日前公告（見 services/mops_fetcher.py 的抓取邏輯），本檔案採「次月
11 日起視為已公開」的簡化規則，不追蹤每檔個股實際公告日（系統未記錄，只有 fetched_at 這種
「我方爬蟲何時抓到」的時間，不是官方公告時間）。
"""
from datetime import date
from typing import List, Optional

from indicators.fundamental import latest_visible_month, revenue_visible_from
from services.chip_provider import ScanContext
from strategies.registry import condition


# 向下相容內部函式名稱
_revenue_visible_from = revenue_visible_from
_latest_visible_month = latest_visible_month


@condition(type="revenue_yoy_decline", min_bars=2)
def revenue_yoy_decline(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """連續 N 個月營收年增率（yoy_percent）低於門檻（賣股策略 設計文件第四節）。

    只在「本交易日新公開了一個月營收」的當天觸發一次，避免同一個公告結果連續多個
    交易日重複判定為成立（cooldown 已有 5 個交易日的去重，這裡再做一層是為了語意正確——
    這是一次性的「消息面」事件，不是每天都在成立的持續性狀態，比照 chip_distribution_top
    的 C1「跌破當天」只在轉折日觸發的慣例）。
    """
    if ctx.market != "tw" or not ctx.revenue:
        return []

    consecutive = params.get("consecutive_months", 2)
    threshold = params.get("yoy_threshold", 0)

    trade_date = date.fromisoformat(ctx.dates[idx])
    latest_month = _latest_visible_month(ctx.revenue, trade_date)
    if latest_month is None:
        return []

    if idx >= 1:
        prev_date = date.fromisoformat(ctx.dates[idx - 1])
        if _latest_visible_month(ctx.revenue, prev_date) == latest_month:
            return []  # 沒有新公告的月份，非轉折日，跳過

    months_sorted = sorted(ctx.revenue.keys())
    end = months_sorted.index(latest_month)
    if end + 1 < consecutive:
        return []  # 資料不足 N 個月，不評估（籌碼選股策略 設計文件第 3.3 節同一原則）
    window_months = months_sorted[end - consecutive + 1: end + 1]

    yoy_values = [ctx.revenue[m].get("yoy_percent") for m in window_months]
    if any(v is None for v in yoy_values):
        return []
    if not all(v < threshold for v in yoy_values):
        return []

    return [{
        "direction": "revenue_yoy_decline",
        "details": {
            "months": window_months,
            "yoy_percent": yoy_values,
            "latest_month": latest_month,
        },
    }]
