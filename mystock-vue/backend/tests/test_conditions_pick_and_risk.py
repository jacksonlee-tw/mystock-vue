import pytest
from datetime import date
from services.chip_provider import ScanContext, KDSeries, PositionContext
from strategies.conditions_pick import valuation_filter, revenue_growth, chip_resonance, stock_pick_resonance, relative_low_zone
from strategies.conditions_risk import trailing_stop, fixed_stop_loss, time_stop


def make_sample_context(
    closes=[100.0, 102.0, 105.0],
    volumes=[1000000, 1200000, 1500000],
    raw_records=None,
    valuation=None,
    revenue_yoy=None,
    revenue_mom=None,
    position=None,
):
    dates = ["2026-06-01", "2026-06-02", "2026-06-03"]
    if raw_records is None:
        raw_records = [
            {"date": d, "close": c, "volume": v, "foreign_buy_sell": 500, "trust_buy_sell": 200}
            for d, c, v in zip(dates, closes, volumes)
        ]
    return ScanContext(
        symbol="2330",
        market="tw",
        name="台積電",
        dates=dates,
        opens=closes,
        highs=closes,
        lows=closes,
        closes=closes,
        volumes=volumes,
        raw_records=raw_records,
        ma={20: [95.0, 96.0, 97.0]},
        valuation=valuation or {"pe_ratio": [12.0, 12.5, 13.0], "pb_ratio": [2.0, 2.1, 2.2], "dividend_yield": [4.5, 4.5, 4.2]},
        revenue_yoy=revenue_yoy or [15.0, 18.0, 22.0],
        revenue_mom=revenue_mom or [3.0, 4.0, 5.0],
        revenue={"2026-05": {"yoy_percent": 22.0, "mom_percent": 5.0}},
        revenue_visible_month=["2026-04", "2026-04", "2026-05"],
        position=position,
    )


def test_valuation_filter():
    ctx = make_sample_context()
    # pe <= 15, yield >= 4% -> should pass
    res = valuation_filter(ctx, 2, {"pe_max": 15.0, "dividend_yield_min": 4.0})
    assert len(res) == 1
    assert res[0]["direction"] == "pick_valuation"

    # pe <= 10 -> should fail
    res_fail = valuation_filter(ctx, 2, {"pe_max": 10.0})
    assert len(res_fail) == 0


def test_revenue_growth():
    ctx = make_sample_context()
    res = revenue_growth(ctx, 2, {"yoy_min": 20.0})
    assert len(res) == 1
    assert res[0]["direction"] == "pick_revenue_growth"

    res_fail = revenue_growth(ctx, 2, {"yoy_min": 30.0})
    assert len(res_fail) == 0


def test_chip_resonance():
    ctx = make_sample_context()
    res = chip_resonance(ctx, 2, {"foreign_consec_days": 2, "trust_consec_days": 2})
    assert len(res) == 1
    assert res[0]["direction"] == "pick_chip_resonance"


def test_stock_pick_resonance():
    # 籌碼門檻改為近 5 日「累計」買超（非單日），需要足夠的歷史 bars 才能算出視窗值
    dates = ["2026-05-28", "2026-05-29", "2026-05-30", "2026-06-01", "2026-06-02"]
    closes = [98.0, 99.0, 100.0, 102.0, 105.0]
    volumes = [1000000, 1000000, 1000000, 1200000, 1500000]
    raw_records = [
        {"date": d, "close": c, "volume": v, "foreign_buy_sell": 500, "trust_buy_sell": 200}
        for d, c, v in zip(dates, closes, volumes)
    ]
    ctx = ScanContext(
        symbol="2330", market="tw", name="台積電",
        dates=dates, opens=closes, highs=closes, lows=closes, closes=closes, volumes=volumes,
        raw_records=raw_records,
        ma={20: [93.0, 94.0, 95.0, 96.0, 97.0]},
        valuation={"pe_ratio": [12.0, 12.2, 12.5, 12.8, 13.0], "pb_ratio": [2.0] * 5, "dividend_yield": [4.5] * 5},
        revenue_yoy=[15.0, 16.0, 18.0, 20.0, 22.0],
        revenue_mom=[3.0, 3.5, 4.0, 4.5, 5.0],
        revenue={"2026-05": {"yoy_percent": 22.0, "mom_percent": 5.0}},
        revenue_visible_month=["2026-04", "2026-04", "2026-04", "2026-05", "2026-05"],
    )
    res = stock_pick_resonance(ctx, 4, {"pe_max": 20.0, "revenue_yoy_min": 15.0})
    assert len(res) == 1
    assert res[0]["direction"] == "pick_resonance"

    # 資料不足 5 日累計視窗時必須跳過、不得誤判成立（§3.3「資料不足即跳過」鐵則的回歸測試）
    short_ctx = make_sample_context()
    res_short = stock_pick_resonance(short_ctx, 2, {"pe_max": 20.0, "revenue_yoy_min": 15.0})
    assert res_short == []


def make_relative_low_zone_context():
    """建構一組「洗盤打底後右側確認」情境（股價相對低點 需求規格書 §4.2）：
    前 50 日持平、中段 20 日下探（拉出季線負乖離）、末 20 日回升並在最後一天帶量站回月線。
    """
    n = 90
    idx = n - 1
    closes = []
    for i in range(n):
        if i < 50:
            closes.append(100.0)
        elif i < 70:
            closes.append(100.0 - (i - 49) * ((100.0 - 63.0) / 20))
        else:
            closes.append(63.0 + (i - 69) * ((82.0 - 63.0) / 20))

    dates = [f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(n)]
    volumes = [10000] * n
    volumes[idx] = 30000  # C6：末日爆量

    raw_records = []
    for i in range(n):
        raw_records.append({
            "date": dates[i],
            "volume": volumes[i],
            # C5：近 10 日融資減 10%（浮額清洗）
            "margin_balance": 100.0 if i < n - 10 else 100.0 - (i - (n - 10) + 1) * 1.0,
            # C5：近 5 日外資皆買超
            "foreign_buy_sell": 50 if i >= idx - 4 else 0,
            "trust_buy_sell": 0,
        })

    def sma(vals, w):
        out, s = [], 0.0
        for i, v in enumerate(vals):
            s += v
            if i >= w:
                s -= vals[i - w]
            out.append(s / w if i >= w - 1 else None)
        return out

    def bias_series(cl, ma):
        return [None if m is None else (c - m) / m * 100 for c, m in zip(cl, ma)]

    ma20, ma60 = sma(closes, 20), sma(closes, 60)
    volume_ma = sma(volumes, 5)

    # C4：K 值近 10 日內曾探至 12（超賣），末日回升至 24
    kd_k = [50.0] * n
    for i in range(idx - 9, idx - 3):
        kd_k[i] = 12.0
    for i in range(idx - 3, n):
        kd_k[i] = 12.0 + (i - (idx - 3)) * 4

    return ScanContext(
        symbol="9999", market="tw", name="測試股",
        dates=dates, opens=closes, highs=closes, lows=closes, closes=closes, volumes=volumes,
        raw_records=raw_records,
        ma={20: ma20, 60: ma60},
        bias={60: bias_series(closes, ma60), 20: bias_series(closes, ma20)},
        volume_ma=volume_ma,
        kd={(9, 3, 3): KDSeries(k=kd_k, d=list(kd_k))},
        valuation={"pe_ratio": [10.0] * n, "pb_ratio": [1.0] * n, "dividend_yield": [5.0] * n},
        revenue={"2026-05": {"yoy_percent": 3.0, "mom_percent": 1.0}, "2026-06": {"yoy_percent": 2.0, "mom_percent": 1.0}},
        revenue_visible_month=["2026-06"] * n,
        revenue_yoy=[2.0] * n,
        revenue_mom=[1.0] * n,
    ), idx


def test_relative_low_zone_fires_when_all_conditions_met():
    ctx, idx = make_relative_low_zone_context()
    res = relative_low_zone(ctx, idx, {})
    assert len(res) == 1
    assert res[0]["direction"] == "pick_relative_low"

    # §5.2：details 必須包含建議動作模板與前端欄位所需的全部鍵
    details = res[0]["details"]
    expected_keys = {
        "close", "pe_ratio", "pb_ratio", "dividend_yield", "yoy_percent", "visible_month",
        "bias_percent", "bias_min_in_window", "kd_k_min_in_window", "margin_change_pct",
        "foreign_buy_days", "trust_buy_days", "ma_period", "ma_value", "volume_ratio",
    }
    assert expected_keys.issubset(details.keys())
    assert details["ma_period"] == 20
    assert details["foreign_buy_days"] == 5


@pytest.mark.parametrize("label,override", [
    ("C1 估值不達標", {"pe_max": 5.0}),
    ("C2 營收守衛不達標", {"revenue_yoy_min": 50.0}),
    ("C3 未達超跌狀態", {"bias_max": -90.0}),
    ("C4 未達動能超賣", {"kd_oversold": 1.0}),
    ("C5 籌碼未洗盤", {"margin_change_max_pct": -50.0}),
    ("C6 未完成右側確認", {"volume_multiple": 100.0}),
])
def test_relative_low_zone_and_short_circuit(label, override):
    """AND 短路回歸測試（§2.2-1／ADR-RL-01）：任一條件不成立，整體不得觸發訊號。"""
    ctx, idx = make_relative_low_zone_context()
    assert relative_low_zone(ctx, idx, override) == [], label


def test_relative_low_zone_requires_and_min_bars_registered():
    """確認條件已依規格 §5.2 註冊正確的 min_bars/requires（scanner.py 的預檢依據）。"""
    from strategies.registry import CONDITION_REGISTRY
    spec = CONDITION_REGISTRY["relative_low_zone"]
    assert spec.min_bars == 60
    assert set(spec.requires) == {"valuation", "revenue_yoy", "raw_records", "kd"}


def test_trailing_stop():
    pos = PositionContext(
        symbol="2330",
        market="tw",
        shares=1000,
        avg_cost=100.0,
        entry_date="2026-06-01",
        holding_trading_days=5,
        peak_close_since_entry=120.0,
        unrealized_return_pct=5.0,
    )
    # Current close is 105.0 -> drawdown from 120 is -12.5%
    ctx = make_sample_context(closes=[120.0, 115.0, 105.0], position=pos)
    res = trailing_stop(ctx, 2, {"drawdown_pct": 10.0})
    assert len(res) == 1
    assert res[0]["direction"] == "exit_trailing_stop"


def test_fixed_stop_loss():
    pos = PositionContext(
        symbol="2330",
        market="tw",
        shares=1000,
        avg_cost=100.0,
        entry_date="2026-06-01",
        holding_trading_days=5,
        peak_close_since_entry=100.0,
        unrealized_return_pct=-10.0,
    )
    # Current close is 90.0 -> loss is -10%
    ctx = make_sample_context(closes=[98.0, 95.0, 90.0], position=pos)
    res = fixed_stop_loss(ctx, 2, {"stop_loss_pct": 8.0})
    assert len(res) == 1
    assert res[0]["direction"] == "exit_stop_loss"


def test_time_stop():
    pos = PositionContext(
        symbol="2330",
        market="tw",
        shares=1000,
        avg_cost=100.0,
        entry_date="2026-03-01",
        holding_trading_days=65,
        peak_close_since_entry=105.0,
        unrealized_return_pct=-2.0,
    )
    ctx = make_sample_context(closes=[100.0, 99.0, 98.0], position=pos)
    res = time_stop(ctx, 2, {"max_holding_days": 60, "min_return_pct": 0.0})
    assert len(res) == 1
    assert res[0]["direction"] == "exit_time_stop"
