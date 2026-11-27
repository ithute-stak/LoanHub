from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from database.models.enums import PaymentDirection, PaymentPurpose, PaymentStatus
from services.principal_x_adjustment_review import review_adjustment_rows


def fixture():
    company, loan, payment_id = uuid4(), uuid4(), uuid4()
    original = SimpleNamespace(
        id=payment_id, company_id=company, loan_id=loan,
        amount=Decimal("100.00"), currency="LSL",
        purpose=PaymentPurpose.LOAN_REPAYMENT,
        direction=PaymentDirection.INBOUND, status=PaymentStatus.REVERSED,
    )
    now = datetime(2026, 1, 1)
    adjustment = SimpleNamespace(
        id=uuid4(), company_id=company, payment_id=payment_id,
        amount=Decimal("100.00"), currency="LSL", adjustment_type="refund",
        status="completed", approval_request_id=uuid4(),
        requested_by_user_id=uuid4(), approved_by_user_id=uuid4(),
        approved_at=now, completed_at=now + timedelta(seconds=1),
    )
    return original, adjustment, dict(company_id=company, loan_id=loan)


def test_consistent_local_adjustment_is_not_external_finality():
    original, adjustment, scope = fixture()
    result = review_adjustment_rows(payments=[original], adjustments=[adjustment], **scope)
    assert result.locally_consistent_count == 1
    assert result.inconsistent_completed_count == 0
    assert result.unresolved_count == 1
    assert result.complete is False


@pytest.mark.parametrize("problem", ["partial", "excess", "currency", "maker_checker", "chronology", "not_reversed", "invalid_amount"])
def test_inconsistent_completed_adjustment_is_flagged(problem):
    original, adjustment, scope = fixture()
    if problem == "partial":
        adjustment.amount = Decimal("50.00")
    elif problem == "excess":
        adjustment.amount = Decimal("100.01")
    elif problem == "currency":
        adjustment.currency = "USD"
    elif problem == "maker_checker":
        adjustment.approved_by_user_id = adjustment.requested_by_user_id
    elif problem == "chronology":
        adjustment.completed_at = adjustment.approved_at - timedelta(seconds=1)
    elif problem == "not_reversed":
        original.status = PaymentStatus.SUCCEEDED
    else:
        adjustment.amount = Decimal("NaN")
    result = review_adjustment_rows(payments=[original], adjustments=[adjustment], **scope)
    assert result.inconsistent_completed_count == 1
    assert result.locally_consistent_count == 0
    assert result.excess_adjustment_original_count == int(problem == "excess")
    assert result.complete is False


def test_multiple_completed_adjustments_exceed_original():
    original, adjustment, scope = fixture()
    second = SimpleNamespace(**vars(adjustment))
    second.id = uuid4()
    result = review_adjustment_rows(payments=[original], adjustments=[adjustment, second], **scope)
    assert result.duplicate_completed_original_count == 1
    assert result.excess_adjustment_original_count == 1
    assert result.complete is False


@pytest.mark.parametrize("status,expected", [("rejected", 0), ("processing", 1)])
def test_noncompleted_adjustments(status, expected):
    original, adjustment, scope = fixture()
    adjustment.status = status
    result = review_adjustment_rows(payments=[original], adjustments=[adjustment], **scope)
    assert result.completed_count == 0
    assert result.unresolved_count == expected


def test_other_company_adjustment_is_rejected():
    original, adjustment, scope = fixture()
    adjustment.company_id = uuid4()
    with pytest.raises(ValueError):
        review_adjustment_rows(payments=[original], adjustments=[adjustment], **scope)
