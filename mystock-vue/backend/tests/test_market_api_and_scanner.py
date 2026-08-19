import pytest
import httpx
from main import app
from strategies.config_loader import load_strategy_config
from strategies.direction import classify_direction, to_signal_type


def test_strategy_config_loader():
    cfg = load_strategy_config()
    assert len(cfg.strategies) > 0
    # Check that stock_picking and risk strategies are loaded
    strat_ids = [s.id for s in cfg.strategies]
    assert "pick_valuation_low_pe" in strat_ids
    assert "pick_revenue_growth_momentum" in strat_ids
    assert "pick_chip_institutional_resonance" in strat_ids
    assert "pick_multi_factor_resonance" in strat_ids
    assert "pick_relative_low_zone" in strat_ids
    assert "exit_trailing_stop" in strat_ids
    assert "exit_fixed_stop_loss" in strat_ids

    relative_low = next(s for s in cfg.strategies if s.id == "pick_relative_low_zone")
    assert relative_low.category == "stock_picking"
    assert relative_low.scope == "universe"
    assert relative_low.conditions[0]["type"] == "relative_low_zone"


def test_direction_classification():
    assert classify_direction("pick_valuation") == "bullish"
    assert to_signal_type("pick_valuation") == "BUY"
    assert classify_direction("exit_trailing_stop") == "bearish"
    assert to_signal_type("exit_trailing_stop") == "SELL"


@pytest.mark.anyio
async def test_fundamentals_compare_api():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/fundamentals/compare?symbols=2330,2317&market=tw")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "rows" in data["data"]
        assert len(data["data"]["rows"]) == 2
        assert data["data"]["rows"][0]["symbol"] == "2330"
