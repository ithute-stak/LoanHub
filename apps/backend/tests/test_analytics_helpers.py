from datetime import date

import pytest
from fastapi import HTTPException

from routers.analytics import _range
from services.analytics_service import (
    _arrears_band,
    _loan_size_band,
    _period_keys,
    _resolve_granularity,
    _term_band,
)


def test_analytics_range_and_granularity():
    start, end = _range(date(2026, 1, 1), date(2026, 1, 30))
    assert start == date(2026, 1, 1)
    assert end == date(2026, 1, 30)
    assert _resolve_granularity(start, end, None) == "day"
    assert _resolve_granularity(date(2026, 1, 1), date(2026, 5, 1), None) == "week"
    assert _resolve_granularity(date(2025, 1, 1), date(2026, 1, 1), None) == "month"


def test_analytics_period_and_business_bands():
    assert len(_period_keys(date(2026, 1, 1), date(2026, 1, 3), "day")) == 3
    assert _loan_size_band(1200) == "LSL 1,000–4,999"
    assert _term_band(6) == "4–6 periods"
    assert _arrears_band(95) == "90+ days"


def test_analytics_rejects_invalid_or_excessive_ranges():
    with pytest.raises(HTTPException):
        _range(date(2026, 2, 1), date(2026, 1, 1))
    with pytest.raises(HTTPException):
        _range(date(2020, 1, 1), date(2026, 1, 1))
