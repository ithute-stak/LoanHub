from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from services.external_underwriting_evidence_service import cdas_deduction_capacity


ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_live_cdas_affordability_is_conservative_with_profile_capacity() -> None:
    profile = SimpleNamespace(
        id="profile",
        verified=True,
        verified_at=None,
        verification_reference="verified",
        employee_number="EMP-100",
        net_salary=Decimal("5000.00"),
        existing_deductions=Decimal("500.00"),
        maximum_deduction_percent=Decimal("40"),
    )

    result = cdas_deduction_capacity(
        profile,
        selected_for_collection=True,
        proposed_installment=Decimal("900.00"),
        application_id="application",
        live_affordability=Decimal("800.00"),
    )

    assert result["calculated_deduction_capacity"] == "1500.00"
    assert result["live_affordability"] == "800.00"
    assert result["available_deduction_capacity"] == "800.00"
    assert result["capacity_source"] == "minimum_of_profile_and_live_cdas"
    assert result["capacity_sufficient"] is False


def test_origination_assessment_requires_credit_bureau_and_live_cdas_for_employee() -> None:
    router = _read(ROOT / "routers/origination.py")
    service = _read(ROOT / "services/origination_service.py")

    assert "async def assess_application(" in router
    assert "CDASPayrollProfile.verified.is_(True)" in router
    assert "await client.check_affordability(" in router
    assert 'operation_type="affordability"' in router
    assert "live_cdas_affordability=live_cdas_affordability" in router

    assert "Credit-bureau integration must be enabled before affordability can be calculated." in service
    assert "A fresh credit-bureau report is required before affordability can be calculated." in service
    assert "if bureau_fresh:" in service
    assert "internal_max_installment" in service
    assert "min(internal_max_installment, money(live_cdas_affordability))" in service
    assert '"cdas_live_affordability_missing"' in service
    assert '"cdas_live_affordability_insufficient"' in service
    assert '"composite_affordability"' in service


def test_employee_number_does_not_silently_fall_back_when_cdas_is_unavailable() -> None:
    router = _read(ROOT / "routers/origination.py")

    assert "except CdasError as exc:" in router
    assert "CDAS affordability could not be verified" in router


def test_bureau_commitments_are_always_counted_when_fresh() -> None:
    service = _read(ROOT / "services/origination_service.py")

    assert "if bureau_fresh:" in service
    assert 'debt_mode = str(bureau_policy.get("bureau_debt_mode") or "max")' in service
    assert '"included_in_affordability": bureau_fresh' in service
