from __future__ import annotations

from services.cdas_borrower_intelligence import calculate_collection_proposal


def test_collection_proposal_uses_current_balance_and_affordability():
    result = calculate_collection_proposal(outstanding=6000, affordability=500)
    assert result["total_outstanding"] == 6000.0
    assert result["available_affordability"] == 500.0
    assert result["suggested_monthly_deduction"] == 500.0
    assert result["estimated_collection_months"] == 12
    assert result["can_add_deduction"] is True


def test_collection_proposal_never_collects_more_than_balance():
    result = calculate_collection_proposal(outstanding=650, affordability=1200)
    assert result["suggested_monthly_deduction"] == 650.0
    assert result["estimated_collection_months"] == 1


def test_small_real_affordability_is_preserved_without_rounding_to_zero():
    result = calculate_collection_proposal(outstanding=6000, affordability="0.15")
    assert result["suggested_monthly_deduction"] == 0.15
    assert result["estimated_collection_months"] == 40000


def test_no_positive_affordability_means_no_new_collection_proposal():
    result = calculate_collection_proposal(outstanding=6000, affordability=0)
    assert result["suggested_monthly_deduction"] == 0.0
    assert result["estimated_collection_months"] is None
    assert result["can_add_deduction"] is False


def test_no_balance_means_no_collection_proposal_even_when_capacity_exists():
    result = calculate_collection_proposal(outstanding=0, affordability=1000)
    assert result["suggested_monthly_deduction"] == 0.0
    assert result["estimated_collection_months"] is None
    assert result["can_add_deduction"] is False
