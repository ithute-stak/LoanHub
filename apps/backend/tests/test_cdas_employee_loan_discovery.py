"""CDAS discovery must never turn a displayed loan into an unauthorized mandate."""
from types import SimpleNamespace

from routers.cdas_api import _employee_cdas_registration_decision


def _loan(*, enabled=True, installment="928.00"):
    return SimpleNamespace(cdas_collection_enabled=enabled, installment_amount=installment)


def _profile(*, verified=True):
    return SimpleNamespace(verified=verified)


def test_existing_loan_visible_but_affordability_blocks_registration():
    allowed, reason = _employee_cdas_registration_decision(
        profile=_profile(), loan=_loan(), affordability="3.31", discovery_reason=""
    )
    assert not allowed
    assert "928.00" in reason
    assert "3.31" in reason


def test_unverified_employment_number_is_discovery_only():
    allowed, reason = _employee_cdas_registration_decision(
        profile=None, loan=_loan(), affordability="3000.00",
        discovery_reason="Loan found, but the employee's CDAS payroll profile must be verified first",
    )
    assert not allowed
    assert "verified" in reason


def test_disabled_cdas_stays_blocked():
    allowed, reason = _employee_cdas_registration_decision(
        profile=_profile(), loan=_loan(enabled=False), affordability="3000.00",
        discovery_reason="Loan found, but CDAS collection has not been enabled for this loan",
    )
    assert not allowed
    assert "enabled" in reason


def test_verified_enabled_loan_with_sufficient_affordability_is_eligible():
    allowed, reason = _employee_cdas_registration_decision(
        profile=_profile(), loan=_loan(), affordability="1000.00", discovery_reason=""
    )
    assert allowed
    assert reason is None


def test_no_loan_is_never_eligible():
    allowed, reason = _employee_cdas_registration_decision(
        profile=_profile(), loan=None, affordability="2000.00",
        discovery_reason="No approved or active company loan found for this employee",
    )
    assert not allowed
    assert "No approved" in reason
