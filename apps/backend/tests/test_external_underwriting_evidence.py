from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from services.external_underwriting_evidence_service import (
    bureau_evidence,
    cdas_deduction_capacity,
    external_evidence_snapshot,
)


def _bureau(**overrides):
    normalized = {
        "defaults_count": 0,
        "judgments_count": 0,
        "collections_count": 0,
        "recent_enquiries_count": 1,
        "identity_match": True,
    }
    normalized.update(overrides.pop("normalized", {}))
    return SimpleNamespace(
        id=uuid4(),
        enquiry_reference="EXP-TEST",
        score=overrides.pop("score", 700),
        risk_grade=overrides.pop("risk_grade", "low"),
        monthly_obligations=Decimal(overrides.pop("monthly_obligations", "900.00")),
        current_exposure=Decimal(overrides.pop("current_exposure", "12000.00")),
        completed_at=datetime.now(timezone.utc),
        response_data={"normalized": normalized},
        **overrides,
    )


def _cdas(**overrides):
    values = {
        "id": uuid4(),
        "verified": True,
        "employee_number": "EMP-1",
        "net_salary": Decimal("5000.00"),
        "existing_deductions": Decimal("1000.00"),
        "maximum_deduction_percent": Decimal("40"),
        "verified_at": datetime.now(timezone.utc),
        "verification_reference": "CDAS-VERIFY-1",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_bureau_policy_can_block_judgments_and_collections() -> None:
    row = _bureau(normalized={"judgments_count": 1, "collections_count": 2})
    result = bureau_evidence(
        row,
        policy={
            "block_judgments": True,
            "block_collections": True,
            "block_defaults": False,
            "require_identity_match": False,
        },
        application_id=uuid4(),
    )

    codes = {item["code"] for item in result["blockers"]}
    assert "judgments_blocked" in codes
    assert "collections_blocked" in codes
    assert result["judgments_count"] == 1
    assert result["collections_count"] == 2


def test_cdas_capacity_is_payroll_gate_not_second_debt_subtraction() -> None:
    result = cdas_deduction_capacity(
        _cdas(),
        selected_for_collection=True,
        proposed_installment=Decimal("1200.00"),
        application_id=uuid4(),
    )

    assert result["maximum_deduction"] == "2000.00"
    assert result["available_deduction_capacity"] == "1000.00"
    assert result["capacity_sufficient"] is False
    assert result["blockers"][0]["code"] == "deduction_capacity_insufficient"


def test_cdas_capacity_passes_when_proposed_installment_fits() -> None:
    result = cdas_deduction_capacity(
        _cdas(),
        selected_for_collection=True,
        proposed_installment=Decimal("900.00"),
        application_id=uuid4(),
    )

    assert result["available_deduction_capacity"] == "1000.00"
    assert result["capacity_sufficient"] is True
    assert result["blockers"] == []


def test_external_snapshot_explicitly_prevents_cdas_double_counting() -> None:
    snapshot = external_evidence_snapshot(
        application_id=uuid4(),
        bureau=_bureau(monthly_obligations="1300.00"),
        bureau_policy={
            "include_bureau_commitments_in_affordability": True,
            "bureau_debt_mode": "max",
        },
        cdas_profile=_cdas(existing_deductions=Decimal("800.00")),
        cdas_selected=True,
        proposed_installment=Decimal("700.00"),
    )

    assert snapshot["debt_counting"]["bureau_commitments_in_affordability"] is True
    assert snapshot["debt_counting"]["bureau_commitments_mode"] == "max"
    assert snapshot["debt_counting"]["cdas_existing_deductions_are_capacity_only"] is True
    assert snapshot["credit_bureau"]["monthly_commitments"] == "1300.00"
    assert snapshot["cdas"]["existing_deductions"] == "800.00"
