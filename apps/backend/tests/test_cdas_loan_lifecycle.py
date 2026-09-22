from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from database.models.cdas_official import CdasOfficialMandateState
from database.models.enums import LoanStatus
from integrations.cdas import CdasError
from routers.cdas_lifecycle import (
    CdasLinkedActionRequest,
    CdasLoanDeductionRegistrationRequest,
    _require_active_lifecycle,
    _require_lifecycle_transition,
)
from services.cdas_deduction_lifecycle import (
    CdasLifecycleError,
    _apply_provider_response,
    _lifecycle_from_code,
    _mark_uncertain_failure,
    _require_maker_checker,
    _validate_settlement_against_loan,
)


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


@pytest.mark.parametrize(
    ("status", "request_type"),
    [
        ("registered", 3),
        ("reserved", 3),
        ("reviewed", 4),
        ("approved", 5),
        ("registered", 6),
        ("reviewed", 6),
        ("approved", 6),
        ("cancelled_or_rejected", 9),
        ("registered", 10),
    ],
)
def test_backend_lifecycle_guard_accepts_valid_transitions(status: str, request_type: int):
    _require_lifecycle_transition(status, request_type)


@pytest.mark.parametrize(
    ("status", "request_type"),
    [
        ("registered", 4),
        ("registered", 5),
        ("reviewed", 5),
        ("active", 3),
        ("active", 4),
        ("active", 6),
        ("settled", 10),
        ("deleted", 9),
        ("reconciliation_required", 4),
    ],
)
def test_backend_lifecycle_guard_rejects_out_of_order_or_terminal_transitions(status: str, request_type: int):
    with pytest.raises(CdasLifecycleError) as raised:
        _require_lifecycle_transition(status, request_type)
    assert raised.value.status_code == 409


@pytest.mark.parametrize("status", ["active", "changed"])
def test_active_only_guard_allows_active_deductions(status: str):
    _require_active_lifecycle(status, "modified")
    _require_active_lifecycle(status, "settled")


@pytest.mark.parametrize("status", ["registered", "reviewed", "approved", "settled", "reconciliation_required"])
def test_active_only_guard_rejects_non_active_deductions(status: str):
    with pytest.raises(CdasLifecycleError) as raised:
        _require_active_lifecycle(status, "modified")
    assert raised.value.status_code == 409


def test_documented_duplicate_status_codes_are_not_overinterpreted():
    assert _lifecycle_from_code(6) == "cancelled_or_rejected"
    assert _lifecycle_from_code(8) == "expired_or_auto_settled"


@pytest.mark.parametrize("status", [401, 402, 406, 417, 419, 500, 503])
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


def _mandate_stub():
    return SimpleNamespace(
        status="registration_submission_pending",
        activated_at=None,
        completed_at=None,
        external_reference=None,
    )


def test_add_update_success_without_documented_status_is_reconciliation_required():
    state = CdasOfficialMandateState(lifecycle_status="registration_submission_pending")
    complete = _apply_provider_response(
        state,
        _mandate_stub(),
        {"DeductionID": 123},
        requested_lifecycle="registered",
        require_status=True,
        require_deduction_id=True,
    )
    assert complete is False
    assert state.requires_reconciliation is True
    assert state.lifecycle_status == "reconciliation_required"


def test_registration_success_requires_deduction_id_and_status():
    state = CdasOfficialMandateState(lifecycle_status="registration_submission_pending")
    mandate = _mandate_stub()
    complete = _apply_provider_response(
        state,
        mandate,
        {"DeductionID": 123, "DeductionStatus": 1, "ReferenceNo": "REF-1"},
        requested_lifecycle="registered",
        require_status=True,
        require_deduction_id=True,
    )
    assert complete is True
    assert state.deduction_id == 123
    assert state.lifecycle_status == "registered"
    assert state.requires_reconciliation is False
    assert mandate.status == "registered"


class _EventQuery:
    def __init__(self, event):
        self.event = event

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.event


def test_registration_maker_cannot_review_or_approve_same_mandate():
    maker = uuid4()
    db = SimpleNamespace(query=lambda *_models: _EventQuery(SimpleNamespace(actor_user_id=maker)))
    for request_type in (3, 4, 5):
        with pytest.raises(CdasLifecycleError) as raised:
            _require_maker_checker(db, state_id=uuid4(), actor_user_id=maker, request_type=request_type)
        assert raised.value.status_code == 409


def test_different_checker_can_review_and_approve():
    maker = uuid4()
    checker = uuid4()
    db = SimpleNamespace(query=lambda *_models: _EventQuery(SimpleNamespace(actor_user_id=maker)))
    _require_maker_checker(db, state_id=uuid4(), actor_user_id=checker, request_type=3)
    _require_maker_checker(db, state_id=uuid4(), actor_user_id=checker, request_type=4)


def test_paid_or_consolidated_settlement_requires_loanhub_debt_to_be_closed():
    active_loan = SimpleNamespace(status=LoanStatus.ACTIVE, balance=Decimal("100.00"))
    for reason in (2, 3):
        with pytest.raises(CdasLifecycleError) as raised:
            _validate_settlement_against_loan(active_loan, reason)
        assert raised.value.status_code == 409

    completed = SimpleNamespace(status=LoanStatus.COMPLETED, balance=Decimal("0.00"))
    _validate_settlement_against_loan(completed, 2)
    _validate_settlement_against_loan(completed, 3)


def test_policy_expiry_or_deceased_settlement_does_not_require_zero_balance():
    active_loan = SimpleNamespace(status=LoanStatus.ACTIVE, balance=Decimal("100.00"))
    _validate_settlement_against_loan(active_loan, 1)
    _validate_settlement_against_loan(active_loan, 4)
