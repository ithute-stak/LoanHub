from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from services.rollover_component_evidence import verify_component_allocation_evidence


def example():
    return SimpleNamespace(principal_due=Decimal("70"), interest_due=Decimal("20"), fee_due=Decimal("10"), total_due=Decimal("100"), paid_amount=Decimal("92"))


def test_verified_split_preserves_outstanding_component_types():
    evidence = dict(principal_paid="70", interest_paid="20", fee_paid="2", source_reference="ALLOC-123", verified_by="user-123")
    result = verify_component_allocation_evidence(installment=example(), evidence=evidence)
    assert result["remaining_principal"] == "0"
    assert result["remaining_interest"] == "0"
    assert result["remaining_fees"] == "8"


def test_missing_or_inconsistent_evidence_is_rejected():
    for evidence in (None, {}, dict(principal_paid="70", interest_paid="20", fee_paid="1", source_reference="ALLOC-123", verified_by="user-123")):
        with pytest.raises(HTTPException):
            verify_component_allocation_evidence(installment=example(), evidence=evidence)
