from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from database.models.enums import PaymentDirection, PaymentPurpose, PaymentStatus
from services.principal_x_local_lifetime_collections import compare_local_lifetime_collections


def evidence():
    company, loan = uuid4(), uuid4()
    cutoff = datetime(2026, 1, 1)
    row = SimpleNamespace(id=uuid4(), company_id=company, loan_id=loan,
        purpose=PaymentPurpose.LOAN_REPAYMENT, direction=PaymentDirection.INBOUND,
        status=PaymentStatus.SUCCEEDED, amount=Decimal("500"), currency="LSL",
        completed_at=cutoff + timedelta(days=1))
    return row, dict(company_id=company, loan_id=loan, recorded_paid="800",
        historical_opening_credit="300", historical_conversion_at=cutoff)


def test_opening_and_live_credit_counted_once():
    row, scope = evidence()
    result = compare_local_lifetime_collections(payments=[row, row], **scope)
    assert result.recorded_successful_repayments == Decimal("500")
    assert result.recorded_credit_before_adjustments == Decimal("800")
    assert result.unexplained_difference == 0
    assert result.unresolved_payment_count == 1
    assert result.authoritative_net_collected is None
    assert result.reconciled is False


@pytest.mark.parametrize("offset", [-1, 0])
def test_preconversion_or_equal_timestamp_excluded(offset):
    row, scope = evidence()
    row.completed_at = scope["historical_conversion_at"].replace(tzinfo=timezone.utc) + timedelta(seconds=offset)
    result = compare_local_lifetime_collections(payments=[row], **scope)
    assert result.recorded_successful_repayments == 0
    assert result.unresolved_payment_count == 1


def test_unknown_opening_never_assumed_zero():
    row, scope = evidence()
    scope["historical_opening_credit"] = None
    result = compare_local_lifetime_collections(payments=[row], **scope)
    assert result.recorded_credit_before_adjustments is None
    assert result.unexplained_difference is None


def test_known_historical_credit_requires_cutoff():
    row, scope = evidence()
    scope["historical_conversion_at"] = None
    with pytest.raises(ValueError):
        compare_local_lifetime_collections(payments=[row], **scope)


@pytest.mark.parametrize("problem", ["refund", "reversed", "currency", "amount", "missing_date"])
def test_unresolved_rows_not_counted(problem):
    row, scope = evidence()
    if problem == "refund":
        row.purpose = PaymentPurpose.REFUND
        row.direction = PaymentDirection.OUTBOUND
    elif problem == "reversed":
        row.status = PaymentStatus.REVERSED
    elif problem == "currency":
        row.currency = "USD"
    elif problem == "amount":
        row.amount = Decimal("500.001")
    else:
        row.completed_at = None
    result = compare_local_lifetime_collections(payments=[row], **scope)
    assert result.recorded_successful_repayments == 0
    assert result.unresolved_payment_count == 1
    assert result.reconciled is False


def test_cross_loan_payment_rejected():
    row, scope = evidence()
    row.loan_id = uuid4()
    with pytest.raises(ValueError):
        compare_local_lifetime_collections(payments=[row], **scope)
