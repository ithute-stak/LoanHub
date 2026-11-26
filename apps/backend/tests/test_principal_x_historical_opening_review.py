import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from services.principal_x_historical_opening_review import review_historical_opening


def evidence(receipts="2100.00"):
    company, loan = uuid4(), uuid4()
    paid = min(Decimal(receipts), Decimal("2000.00"))
    excess = Decimal(receipts) - paid
    terms = dict(source="legacy_cashout_book", historical_record=True,
                 principal_amount="1000.00", total_repayable="2400.00",
                 duple_morule_limit="2000.00", amount_paid_at_migration=str(paid),
                 receipt_book_total_paid=receipts, overpayment_for_reconciliation=str(excess))
    capture = SimpleNamespace(company_id=company, loan_id=loan, status="posted",
        converted_at=datetime.now(timezone.utc), borrowed_amount=Decimal("1000"),
        total_repayable=Decimal("2400"), amount_paid=Decimal(receipts),
        conversion_data=dict(conversion_type="historical_opening_balance",
            contract_number="LEG-1", payment_transactions_created=0,
            receipt_book_total_paid=receipts, overpayment_for_reconciliation=str(excess)))
    contract = SimpleNamespace(company_id=company, loan_id=loan, status="historical_record",
        contract_number="LEG-1", terms_snapshot=terms,
        contract_hash=hashlib.sha256(json.dumps(terms, sort_keys=True, separators=(",", ":")).encode()).hexdigest())
    return dict(company_id=company, loan_id=loan, capture=capture, contract=contract)


@pytest.mark.parametrize("receipts,credited,excess", [
    ("0.00", "0.00", "0.00"), ("500.00", "500.00", "0.00"),
    ("2100.00", "2000.00", "100.00"),
])
def test_historical_opening_preserves_receipts_separately(receipts, credited, excess):
    result = review_historical_opening(**evidence(receipts))
    assert result.credited_at_migration == Decimal(credited)
    assert result.receipt_book_total == Decimal(receipts)
    assert result.excess_for_review == Decimal(excess)
    assert result.independently_verified is False
    assert result.can_post is False


@pytest.mark.parametrize("problem", ["scope", "draft", "hash", "duplicate_cash", "amount"])
def test_historical_opening_rejects_inconsistent_evidence(problem):
    data = evidence()
    capture, contract = data["capture"], data["contract"]
    if problem == "scope":
        contract.company_id = uuid4()
    elif problem == "draft":
        capture.status = "reviewed"
    elif problem == "hash":
        contract.terms_snapshot["amount_paid_at_migration"] = "1.00"
    elif problem == "duplicate_cash":
        capture.conversion_data["payment_transactions_created"] = 1
    else:
        capture.amount_paid = Decimal("100.00")
    with pytest.raises(ValueError):
        review_historical_opening(**data)


@pytest.mark.parametrize("recorded,expected_difference", [
    ("800.00", "0.00"), ("850.00", "50.00"), ("750.00", "-50.00"),
])
def test_historical_live_comparison_counts_opening_once(recorded, expected_difference):
    from datetime import timedelta
    from database.models.enums import PaymentDirection, PaymentPurpose, PaymentStatus
    from services.principal_x_historical_opening_review import compare_historical_live_payments

    data = evidence("500.00")
    opening = review_historical_opening(**data)
    row = SimpleNamespace(
        id=uuid4(), company_id=data["company_id"], loan_id=data["loan_id"],
        purpose=PaymentPurpose.LOAN_REPAYMENT, status=PaymentStatus.SUCCEEDED,
        direction=PaymentDirection.INBOUND, amount=Decimal("300.00"), currency="LSL",
        completed_at=opening.converted_at + timedelta(days=1),
    )
    result = compare_historical_live_payments(
        opening=opening, recorded_paid=recorded, payments=[row],
        company_id=data["company_id"], loan_id=data["loan_id"],
    )
    assert result.recorded_live_repayments == Decimal("300.00")
    assert result.difference == Decimal(expected_difference)
    assert result.unresolved_rows == 0
    assert result.independently_verified is False


@pytest.mark.parametrize("problem", ["duplicate", "before_conversion", "refund", "currency", "missing_date", "scope"])
def test_historical_live_comparison_does_not_trust_unresolved_payments(problem):
    from datetime import timedelta
    from database.models.enums import PaymentDirection, PaymentPurpose, PaymentStatus
    from services.principal_x_historical_opening_review import compare_historical_live_payments

    data = evidence("500.00")
    opening = review_historical_opening(**data)
    row = SimpleNamespace(
        id=uuid4(), company_id=data["company_id"], loan_id=data["loan_id"],
        purpose=PaymentPurpose.LOAN_REPAYMENT, status=PaymentStatus.SUCCEEDED,
        direction=PaymentDirection.INBOUND, amount=Decimal("300.00"), currency="LSL",
        completed_at=opening.converted_at + timedelta(days=1),
    )
    rows = [row]
    if problem == "duplicate":
        rows.append(row)
    elif problem == "before_conversion":
        row.completed_at = opening.converted_at - timedelta(seconds=1)
    elif problem == "refund":
        row.purpose = PaymentPurpose.REFUND
        row.direction = PaymentDirection.OUTBOUND
    elif problem == "currency":
        row.currency = "USD"
    elif problem == "missing_date":
        row.completed_at = None
    else:
        row.company_id = uuid4()
    kwargs = dict(opening=opening, recorded_paid="800.00", payments=rows,
                  company_id=data["company_id"], loan_id=data["loan_id"])
    if problem == "scope":
        with pytest.raises(ValueError):
            compare_historical_live_payments(**kwargs)
    else:
        result = compare_historical_live_payments(**kwargs)
        assert result.unresolved_rows == 1
        assert result.recorded_live_repayments == Decimal("300.00" if problem == "duplicate" else "0.00")
        assert result.independently_verified is False
