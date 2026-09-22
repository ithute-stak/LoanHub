from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from integrations.cdas import CdasError
from routers.cdas_lifecycle import (
    CdasLinkedActionRequest,
    CdasLoanDeductionRegistrationRequest,
)
from services.cdas_deduction_lifecycle import (
    _lifecycle_from_code,
    _mark_uncertain_failure,
)
from database.models.cdas_official import CdasOfficialMandateState


def _registration(**overrides):
    payload = {
        "loan_id": "11111111-1111-1111-1111-111111111111",
        "employee_no": "EMP001",
        "item_code": "ITEM",
        "reference_no": "LH-REF-001",
        "loan_policy": 1,
        "deduction_amount": Decimal("500.00"),
        "principal_amount": Decimal("6000.00"),
        "total_installment": 12,
        "effective_month": "2026-10",
        "borrower_consent": True,
    }
    payload.update(overrides)
    return CdasLoanDeductionRegistrationRequest(**payload)


def test_registration_requires_positive_installments_and_consent_field():
    request = _registration()
    assert request.total_installment == 12
    assert request.borrower_consent is True

    with pytest.raises(ValidationError):
        _registration(total_installment=0)

    with pytest.raises(ValidationError):
        CdasLoanDeductionRegistrationRequest(
            **{key: value for key, value in request.model_dump().items() if key != "borrower_consent"}
        )


def test_registration_requires_documented_effective_month_shape():
    with pytest.raises(ValidationError):
        _registration(effective_month="10/2026")
    with pytest.raises(ValidationError):
        _registration(effective_month="2026-13")


@pytest.mark.parametrize("request_type", [3, 4, 5, 6, 9, 10])
def test_linked_action_accepts_only_non_registration_non_settlement_mutations(request_type: int):
    assert CdasLinkedActionRequest(request_type=request_type).request_type == request_type


@pytest.mark.parametrize("request_type", [1, 2, 7, 8])
def test_linked_action_rejects_unsafe_or_dedicated_request_types(request_type: int):
    with pytest.raises(ValidationError):
        CdasLinkedActionRequest(request_type=request_type)


def test_documented_duplicate_status_codes_are_not_overinterpreted():
    assert _lifecycle_from_code(6) == "cancelled_or_rejected"
    assert _lifecycle_from_code(8) == "expired_or_auto_settled"


@pytest.mark.parametrize("status", [401, 402, 500, 503])
def test_uncertain_write_failures_require_reconciliation(status: int):
    state = CdasOfficialMandateState(lifecycle_status="registered")
    _mark_uncertain_failure(state, CdasError(status, "provider failure"))
    assert state.requires_reconciliation is True
    assert state.lifecycle_status == "reconciliation_required"


def test_documented_validation_failure_does_not_force_reconciliation():
    state = CdasOfficialMandateState(lifecycle_status="registration_pending")
    _mark_uncertain_failure(state, CdasError(499, "affordability exceeded"))
    assert state.requires_reconciliation is False
    assert state.lifecycle_status == "registration_pending"
