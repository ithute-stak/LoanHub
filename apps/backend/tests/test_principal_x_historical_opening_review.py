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
