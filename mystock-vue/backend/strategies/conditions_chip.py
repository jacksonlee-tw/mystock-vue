"""籌碼選股策略 設計文件第 5.5 節：型態警示（Pattern Alerts）三策略的實作。

只涵蓋不需要「選股池市值分層」（設計文件第 4 節 universe）的策略。核心策略
（外資大型權值波段 core_foreign_largecap / 投信中小型作帳 satellite_trust_window）
依賴 large_cap / mid_small_cap 選股池，該模組尚未建立，故本檔案暫不實作，
待 universe/ 模組完成後再補上（見設計文件 Phase 2）。

沿用 conditions_tech.py 的慣例：函式簽章 (ctx, idx, params) -> List[dict]，
均線/乖離只讀 ctx.ma / ctx.bias，籌碼衍生指標只讀 indicators/chip.py 算好的值，
不在這裡自己加減乘除（策略管理架構 設計文件第 9 節鐵則）；資料不足一律回傳
空列表跳過，不拋例外（滿足 NF-2）。

三個策略的多個子條件（C1/C2/C3…）都在同一個函式內用 AND 組合——這是刻意比照
現有引擎的實際執行模型：scanner.py 對同一策略底下的多個 YAML conditions 項目是
各自獨立觸發（OR），不是 AND；均線策略也一律把「同時成立」的邏輯寫在函式內部
（見 alignment()、squeeze_breakout()），這裡保持同一慣例。

除權息還原（設計文件第 3.4 節）本階段不做——這是繼承 conditions_tech.py 本來就有
的既有限制（ctx.closes 本來就是未還原價），不是本次新增的缺陷。
"""
from typing import List

import indicators.chip as chip
from services.chip_provider import ScanContext
from strategies.registry import condition


@condition(type="chip_bottom_turnover", min_bars=25)
def chip_bottom_turnover(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """底部換手（洗盤）：站上均線 + 融資退場 + 法人進場（籌碼選股策略 設計文件第 5.5 節）。"""
    if ctx.market != "tw":
        return []

    ma_period = params.get("ma_period", 20)
    lookback = params.get("lookback_below_days", 20)
    margin_window = params.get("margin_change_window", 20)
    margin_max_pct = params.get("margin_change_max_pct", -5)
    inst_window = params.get("institutional_window", 5)
    consec_days = params.get("consec_buy_days", 3)

    series = ctx.ma.get(ma_period)
    if not series or idx < lookback:
        return []

    close, ma_now = ctx.closes[idx], series[idx]
    if close is None or ma_now is None or close <= ma_now:
        return []

    # C1：近 lookback 日內須曾跌破均線，純粹盤整站上不算「換手」
    was_below = any(
        ctx.closes[j] is not None and series[j] is not None and ctx.closes[j] < series[j]
        for j in range(idx - lookback, idx)
    )
    if not was_below:
        return []

    # C2：融資退場
    margin_change = chip.change_pct(ctx.raw_records, "margin_balance", idx, margin_window)
    if margin_change is None or margin_change > margin_max_pct:
        return []

    # C3：法人進場
    inst_cum = chip.cum_net(ctx.raw_records, "institutional_total", idx, inst_window)
    if inst_cum is None or inst_cum <= 0:
        return []
    foreign_consec = chip.consec_net_buy(ctx.raw_records, "foreign_buy_sell", idx)
    trust_consec = chip.consec_net_buy(ctx.raw_records, "trust_buy_sell", idx)
    if foreign_consec < consec_days and trust_consec < consec_days:
        return []

    return [{
        "direction": "bottom_turnover",
        "details": {
            "close": close,
            "ma_period": ma_period,
            "ma_value": ma_now,
            "margin_change_pct": round(margin_change, 2),
            "institutional_cum_net_lots": inst_cum,
            "foreign_consec_buy_days": foreign_consec,
            "trust_consec_buy_days": trust_consec,
        },
    }]


@condition(type="chip_short_squeeze", min_bars=25)
def chip_short_squeeze(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """高檔軋空（暴走）（籌碼選股策略 設計文件第 5.5 節）。

    v1 簡化：文件的 C3a 依市值分層（大/中/小型股門檻 3%/5%/8%），需要選股池的
    mcap_rank，本階段沒有選股池，故只用單一預設門檻（YAML 參數
    short_margin_ratio_min_pct，預設取文件中型股門檻 5%），搭配不需要排名的 C3b
    相對百分位，兩者任一成立即可；待 universe 模組完成後改為正式分層覆寫。
    """
    if ctx.market != "tw":
        return []

    ma_period = params.get("ma_period", 20)
    slope_window = params.get("ma_slope_window", 5)
    inst_window = params.get("institutional_window", 5)
    inst_min_days = params.get("institutional_min_buy_days", 3)
    ratio_min_pct = params.get("short_margin_ratio_min_pct", 5)
    pct_window = params.get("short_margin_ratio_percentile_window", 60)
    pct_threshold = params.get("short_margin_ratio_percentile", 90)
    short_window = params.get("short_change_window", 5)
    short_min_pct = params.get("short_change_min_pct", 30)

    series = ctx.ma.get(ma_period)
    if not series or idx < slope_window:
        return []
    close, ma_now, ma_prev = ctx.closes[idx], series[idx], series[idx - slope_window]
    if close is None or ma_now is None or ma_prev is None:
        return []
    if close <= ma_now or (ma_now - ma_prev) <= 0:
        return []  # C1：站上均線且均線上彎

    inst_cum = chip.cum_net(ctx.raw_records, "institutional_total", idx, inst_window)
    inst_days = chip.net_buy_days(ctx.raw_records, "institutional_total", idx, inst_window)
    if inst_cum is None or inst_cum <= 0 or inst_days is None or inst_days < inst_min_days:
        return []  # C2：法人續買

    ratio_now = chip.short_margin_ratio(ctx.raw_records, idx)
    if ratio_now is None:
        return []
    ratio_p90 = chip.rolling_percentile(ctx.raw_records, idx, pct_window, pct_threshold)
    tiered_ok = ratio_now >= ratio_min_pct
    percentile_ok = ratio_p90 is not None and ratio_now >= ratio_p90
    if not (tiered_ok or percentile_ok):
        return []  # C3a OR C3b：券資比高檔

    short_change = chip.change_pct(ctx.raw_records, "short_balance", idx, short_window)
    if short_change is None or short_change < short_min_pct:
        return []  # C4：融券激增

    return [{
        "direction": "short_squeeze",
        "details": {
            "close": close,
            "ma_period": ma_period,
            "ma_value": ma_now,
            "institutional_cum_net_lots": inst_cum,
            "institutional_buy_days": inst_days,
            "short_margin_ratio": round(ratio_now, 2),
            "short_margin_ratio_p90": round(ratio_p90, 2) if ratio_p90 is not None else None,
            "short_change_pct": round(short_change, 2),
        },
    }]


@condition(type="chip_distribution_top", min_bars=60)
def chip_distribution_top(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """高檔出貨（崩盤前）（籌碼選股策略 設計文件第 5.5 節）。

    min_bars=60 是刻意設得比其他型態警示（25）高——C3 本身就需要 60 筆融資餘額
    歷史才有意義，資料不足 60 筆時本策略本來就不該觸發，不是 bug。
    """
    if ctx.market != "tw":
        return []
    if idx < 1:
        return []

    ma_period = params.get("ma_period", 20)
    consec_days = params.get("consec_sell_days", 3)
    margin_window = params.get("margin_high_window", 60)

    series = ctx.ma.get(ma_period)
    if not series:
        return []
    close, prev_close = ctx.closes[idx], ctx.closes[idx - 1]
    ma_now, ma_prev = series[idx], series[idx - 1]
    if None in (close, prev_close, ma_now, ma_prev):
        return []
    if not (prev_close >= ma_prev and close < ma_now):
        return []  # C1：跌破均線（比照 conditions_tech.py 的 cross_under 寫法）

    inst_sell_days = chip.consec_net_sell(ctx.raw_records, "institutional_total", idx)
    if inst_sell_days < consec_days:
        return []  # C2：法人連賣

    margin_high = chip.rolling_max(ctx.raw_records, "margin_balance", idx, margin_window)
    margin_now = ctx.raw_records[idx].get("margin_balance") or 0
    if margin_high is None or margin_now < margin_high:
        return []  # C3：融資創高（散戶接手）

    return [{
        "direction": "distribution_top",
        "details": {
            "close": close,
            "ma_period": ma_period,
            "ma_value": ma_now,
            "institutional_consec_sell_days": inst_sell_days,
            "margin_balance": margin_now,
            "margin_high": margin_high,
        },
    }]
