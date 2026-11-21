"""In-memory regression tests for early-settlement reversal state restoration.

These exercise the service function but do not substitute for PostgreSQL
transactional integration tests.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from database.models.enums import InstallmentStatus, LoanStatus
from services import early_settlement_service as service


class LockedQuery:
    def __init__(self, result):
        self.result = result
        self.locked = False

    def filter(self, *args):
        return self

    def with_for_update(self):
        self.locked = True
        return self

    def first(self):
        assert self.locked, "Financial rows must be locked"
        return self.result


class FakeSession:
    def __init__(self, loan, quote):
        self.loan = loan
        self.quote = quote
        self.added = []
        self.queries = []

    def query(self, model):
        self.queries.append(model.__name__)
        if model.__name__ == "LoanEarlySettlement":
            return LockedQuery(self.quote)
        if model.__name__ == "ClientCompanyLoan":
            return LockedQuery(self.loan)
        raise AssertionError(f"Unexpected model: {model}")

    def add(self, item):
        self.added.append(item)


@pytest.mark.parametrize("retained_cents", ["0.08", "0.40"])
def test_reversal_restores_paid_cents_and_loan_snapshot(monkeypatch, retained_cents):
    installment_id = uuid4()
    original_paid_at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    installment = SimpleNamespace(
        id=installment_id,
        status=InstallmentStatus.WAIVED,
        paid_amount=Decimal(retained_cents),
        paid_at=original_paid_at,
        is_superseded=True,
        superseded_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
    )
    loan = SimpleNamespace(
        id=uuid4(),
        installments=[installment],
        status=LoanStatus.COMPLETED,
        total_repayable=Decimal("1000.00"),
        amount_paid=Decimal("1000.00"),
        balance=Decimal("0.00"),
        maturity_date=date(2026, 11, 1),
        repayment_period=1,
        installment_amount=Decimal("1000.00"),
        calculation_breakdown={"early_settlement": {"test": True}},
    )
    quote = SimpleNamespace(
        id=uuid4(),
        loan_id=loan.id,
        status="settled",
        original_total_repayable=Decimal("1500.00"),
        original_amount_paid=Decimal("500.00"),
        original_balance=Decimal("1000.00"),
        original_maturity_date=date(2027, 1, 15),
        original_term_months=6,
        calculation_snapshot={"loan_snapshot": {
            "status": LoanStatus.ACTIVE.value,
            "total_repayable": "1500.00",
            "amount_paid": "500.00",
            "balance": "1000.00",
            "maturity_date": "2027-01-15",
            "repayment_period": 6,
            "installment_amount": "250.00",
            "calculation_breakdown": {"source": "legacy_cashout_book"},
        }},
        installment_snapshot=[{
            "id": str(installment_id),
            "status": InstallmentStatus.PARTIALLY_PAID.value,
            "paid_amount": retained_cents,
            "paid_at": original_paid_at.isoformat(),
            "is_superseded": False,
            "superseded_at": None,
        }],
        reversed_at=None,
    )
    monkeypatch.setattr(service, "_quote_from_payment", lambda db, payment: quote)
    db = FakeSession(loan, quote)
    assert service.reverse_early_settlement(db, SimpleNamespace()) is True
    assert loan.status == LoanStatus.ACTIVE
    assert loan.amount_paid == Decimal("500.00")
    assert loan.balance == Decimal("1000.00")
    assert loan.calculation_breakdown == {"source": "legacy_cashout_book"}
    assert installment.status == InstallmentStatus.PARTIALLY_PAID
    assert installment.paid_amount == Decimal(retained_cents)
    assert installment.paid_at == original_paid_at
    assert installment.is_superseded is False
    assert installment.superseded_at is None
    assert quote.status == "reversed"
    assert quote.reversed_at is not None
    assert db.added == [quote]
    assert db.queries == ["LoanEarlySettlement", "ClientCompanyLoan"]
    assert service.reverse_early_settlement(db, SimpleNamespace()) is False
    assert db.queries == ["LoanEarlySettlement", "ClientCompanyLoan", "LoanEarlySettlement"]
