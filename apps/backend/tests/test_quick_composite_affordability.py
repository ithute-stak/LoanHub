from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_quick_marketplace_affordability_requires_fresh_bureau_and_live_cdas_for_employee() -> None:
    router = _read(ROOT / "routers/loan_offers.py")
    service = _read(ROOT / "services/quick_loan_affordability_service.py")
    policy = _read(ROOT / "services/credit_bureau_policy_service.py")

    assert "async def _quick_affordability_for_terms(" in router
    assert "latest_fresh_borrower_experian_enquiry(" in router
    assert "A fresh credit-bureau report is required before quick affordability can be calculated." in router
    assert "CDASPayrollProfile.verified.is_(True)" in router
    assert "await client.check_affordability(" in router
    assert "CDAS affordability could not be verified" in router
    assert "bureau_evidence(" in router
    assert 'if bureau_policy_evidence["blockers"]:' in router

    assert "bureau_monthly_commitments: Decimal | None = None" in service
    assert "live_cdas_affordability: Decimal | None = None" in service
    assert "debt = max(profile_debt, bureau_debt)" in service
    assert "min(internal_maximum_affordable_installment, _money(live_cdas_affordability))" in service
    assert '"input_source": "composite_external_affordability"' in service

    assert "def latest_fresh_borrower_experian_enquiry(" in policy


def test_quick_offer_preview_create_and_edit_all_await_same_composite_engine() -> None:
    router = _read(ROOT / "routers/loan_offers.py")

    assert "async def preview_quick_loan_affordability(" in router
    assert "async def create_offer(" in router
    assert "async def update_offer(" in router
    assert router.count("await _quick_affordability_for_terms(") == 3
    assert router.count("actor_user_id=context.user.id") >= 3


def test_quick_cdas_affordability_read_is_payg_and_actor_attributed() -> None:
    router = _read(ROOT / "routers/loan_offers.py")

    assert 'operation_type="affordability"' in router
    assert "record_successful_operation(" in router
    assert "actor_user_id=actor_user_id" in router
    assert '"request_origin": "marketplace_quick_affordability"' in router
