import pytest
from datetime import date
from services.valuation_fetcher import _clean_float, ValuationFetcher
from services.revenue_market_fetcher import _normalize_year_month, _clean_int, RevenueMarketFetcher


def test_clean_float():
    assert _clean_float("12.34") == 12.34
    assert _clean_float("1,234.56") == 1234.56
    assert _clean_float("-") is None
    assert _clean_float("N/A") is None
    assert _clean_float(None) is None


def test_normalize_year_month():
    assert _normalize_year_month("11506") == "2026-06"
    assert _normalize_year_month("115/06") == "2026-06"
    assert _normalize_year_month("115-06") == "2026-06"
    assert _normalize_year_month("2026-06") == "2026-06"
    assert _normalize_year_month("202606") == "2026-06"
    assert _normalize_year_month("") is None


def test_clean_int():
    assert _clean_int("1,234,567") == 1234567
    assert _clean_int(1234) == 1234
    assert _clean_int("-") is None
