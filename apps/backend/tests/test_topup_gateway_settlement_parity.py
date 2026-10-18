"""Gateway success must settle the same quoted amount as cash top-ups."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import LoanStatus
from services import lelefa_paygate_service as gateway


class Query:
    def __init__(self, row):
        self.row = row

    def filter(self, *_args):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self.row


class Db:
    def __init__(self, parent, existing=None):
        self.parent = parent
        self.existing = existing
        self.added = []

    def query(self, model):
        if model.__name__ == "LoanTopUpSettlement":
            return Query(self.existing)
        if model.__name__ == "ClientCompanyLoan":
            return Query(self.parent)
        raise AssertionError(model)

    def add(self, obj):
        self.added.append(obj)


def make_case():
    company, borrower = uuid4(), uuid4()
    parent = SimpleNamespace(
        id=uuid4(), company_id=company, borrower_id=borrower,
        status=LoanStatus.ACTIVE, balance=Decimal("1320"),
        amount_paid=Decimal("0"), total_repayable=Decimal("1320"),
        loan_reference="OLD-1",
    )
    loan = SimpleNamespace(
        id=uuid4(), is_top_up=True, parent_loan_id=parent.id,
        company_id=company, borrower_id=borrower,
        principal_amount=Decimal("1200"), top_up_settlement_amount=Decimal("1000"),
        loan_reference="NEW-1",
    )
    payment = SimpleNamespace(
        loan=loan, loan_id=loan.id, amount=Decimal("200"),
        completed_at=None, initiated_by_user_id=uuid4(),
    )
    return Db(parent), payment


def test_gateway_success_records_earned_interest_quote_and_preserves_paid(monkeypatch):
    db, payment = make_case()
    monkeypatch.setattr(
        "services.top_up_settlement.preview_top_up_settlement",
        lambda *_args, **_kwargs: SimpleNamespace(
            settlement_amount=Decimal("1000"), calculation_method="micro_loan",
            unearned_interest_rebate=Decimal("320"),
        ),
    )
    gateway._finalize_top_up(db, payment)
    assert len(db.added) == 1
    settlement = db.added[0]
    assert settlement.settlement_amount == Decimal("1000")
    assert settlement.cash_to_borrower == Decimal("200")
    assert db.parent.amount_paid == Decimal("0")
    assert db.parent.balance == Decimal("0")
    assert db.parent.status == LoanStatus.COMPLETED
    assert "unearned_interest_rebate=320" in settlement.notes


def test_gateway_rejects_changed_quote_before_modifying_parent(monkeypatch):
    db, payment = make_case()
    monkeypatch.setattr(
        "services.top_up_settlement.preview_top_up_settlement",
        lambda *_args, **_kwargs: SimpleNamespace(
            settlement_amount=Decimal("1050"), calculation_method="micro_loan",
            unearned_interest_rebate=Decimal("270"),
        ),
    )
    with pytest.raises(HTTPException) as err:
        gateway._finalize_top_up(db, payment)
    assert err.value.status_code == 409
    assert not db.added
    assert db.parent.balance == Decimal("1320")
    assert db.parent.status == LoanStatus.ACTIVE


def test_gateway_rejects_mismatched_company_before_settlement(monkeypatch):
    db, payment = make_case()
    payment.loan.company_id = uuid4()
    with pytest.raises(HTTPException) as err:
        gateway._finalize_top_up(db, payment)
    assert err.value.status_code == 409
    assert not db.added


def test_gateway_rejects_incorrect_cash_amount_before_settlement():
    db, payment = make_case()
    payment.amount = Decimal("300")
    with pytest.raises(HTTPException) as err:
        gateway._finalize_top_up(db, payment)
    assert err.value.status_code == 409
    assert not db.added
