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


def test_management_command_intelligence_is_ranked_evidence_based_and_human_review_only():
    root = __import__("pathlib").Path(__file__).resolve().parents[2]
    service = (root / "backend" / "services" / "analytics_service.py").read_text(encoding="utf-8")
    router = (root / "backend" / "routers" / "analytics.py").read_text(encoding="utf-8")
    frontend_api = (root / "frontend" / "api" / "analytics.ts").read_text(encoding="utf-8")
    panel = (root / "frontend" / "components" / "company" / "management-command-intelligence-panel.tsx").read_text(encoding="utf-8")
    command = (root / "frontend" / "app" / "(dashboard)" / "company" / "command-centre" / "page.tsx").read_text(encoding="utf-8")

    assert "def build_management_command_intelligence(" in service
    assert "enterprise_early_warning(" in service
    assert '"priority_actions"' in service
    assert '"recommended_action"' in service
    assert '"decision_mode": "human_review"' in service
    assert '"opportunities"' in service
    assert "does not approve loans, move money, post journals" in service
    assert '@router.get("/company-command")' in router
    assert "ManagementCommandIntelligence" in frontend_api
    assert "Management Command Intelligence" in panel
    assert "Ranked management action queue" in panel
    assert "Recommended management action" in panel
    assert "ManagementCommandIntelligencePanel" in command
