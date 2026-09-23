from datetime import date

import pytest

from routers.cdas_daily_intelligence import _next_month, build_registration_draft_math, router


def test_registration_draft_math_caps_deduction_at_outstanding_balance():
    deduction, installments = build_registration_draft_math(
        outstanding=500,
        affordability=900,
    )
    assert float(deduction) == 500.0
    assert installments == 1


def test_registration_draft_math_uses_available_capacity_and_rounds_term_up():
    deduction, installments = build_registration_draft_math(
        outstanding=1000,
        affordability=300,
    )
    assert float(deduction) == 300.0
    assert installments == 4


def test_registration_draft_math_rejects_missing_capacity_or_balance():
    with pytest.raises(ValueError):
        build_registration_draft_math(outstanding=1000, affordability=0)
    with pytest.raises(ValueError):
        build_registration_draft_math(outstanding=0, affordability=1000)


def test_registration_draft_math_enforces_600_installment_safety_limit():
    with pytest.raises(ValueError, match="600-installment"):
        build_registration_draft_math(outstanding=601, affordability=1)


def test_next_month_rolls_december_into_next_year():
    assert _next_month(date(2026, 11, 15)) == "2026-12"
    assert _next_month(date(2026, 12, 15)) == "2027-01"


def test_daily_intelligence_hardening_routes_are_registered_on_child_router():
    paths = {route.path for route in router.routes}
    assert "/cdas/daily-intelligence/status" in paths
    assert "/cdas/daily-intelligence/opportunities/{opportunity_id}/registration-draft" in paths
