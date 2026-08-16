import pytest
from datetime import date
from services.chip_provider import ScanContext, PositionContext
from strategies.conditions_pick import valuation_filter, revenue_growth, chip_resonance, stock_pick_resonance
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
