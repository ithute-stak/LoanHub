"""Local state fingerprints are read-only, deterministic, and loan scoped."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from database.models.cash import CashTransaction
from database.models.payment import PaymentTransaction
from database.models.repayment import PaymentAllocation
from database.models.treasury import TreasuryEntry
from services.principal_x_locked_source_revision import local_principal_x_source_revision


class Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def join(self, *args):
        return self

    def all(self):
        return self.rows


class Session:
    def __init__(self, payments, cash=(), allocations=(), treasury=()):
        self.data = {
            PaymentTransaction: list(payments), CashTransaction: list(cash),
            PaymentAllocation: list(allocations), TreasuryEntry: list(treasury),
        }

    def query(self, model):
        return Query(self.data[model])


def test_empty_local_sources_have_stable_but_non_authoritative_revision():
    company_id, loan_id = uuid4(), uuid4()
    first = local_principal_x_source_revision(
        Session([]), company_id=company_id, loan_id=loan_id,
    )
    second = local_principal_x_source_revision(
        Session([]), company_id=company_id, loan_id=loan_id,
    )
    assert first == second
    assert len(first) == 64
    assert first != local_principal_x_source_revision(
        Session([]), company_id=uuid4(), loan_id=loan_id,
    )


def test_financial_state_changes_invalidate_revision():
    company_id, loan_id, payment_id = uuid4(), uuid4(), uuid4()
    row = SimpleNamespace(
        id=payment_id, company_id=company_id, loan_id=loan_id,
        amount=Decimal("100.00"), currency="LSL", status="succeeded",
        direction="inbound", purpose="loan_repayment",
    )
    before = local_principal_x_source_revision(
        Session([row]), company_id=company_id, loan_id=loan_id,
    )
    row.amount = Decimal("99.00")
    after = local_principal_x_source_revision(
        Session([row]), company_id=company_id, loan_id=loan_id,
    )
    assert before != after


def test_treasury_status_and_refund_evidence_change_revision():
    company_id, loan_id, payment_id = uuid4(), uuid4(), uuid4()
    posted = SimpleNamespace(
        id=uuid4(), company_id=company_id, loan_id=loan_id,
        payment_transaction_id=payment_id, amount=Decimal("10.00"),
        currency="LSL", approval_status="posted", is_voided=False,
        direction="money_out", entry_type="refund",
    )
    session = Session([], treasury=[posted])
    first = local_principal_x_source_revision(
        session, company_id=company_id, loan_id=loan_id,
    )
    posted.is_voided = True
    second = local_principal_x_source_revision(
        session, company_id=company_id, loan_id=loan_id,
    )
    assert first != second


def test_order_does_not_change_revision_but_duplicate_rows_do():
    company_id, loan_id = uuid4(), uuid4()
    row1 = SimpleNamespace(id=uuid4(), amount=Decimal("1.00"))
    row2 = SimpleNamespace(id=uuid4(), amount=Decimal("2.00"))
    a = local_principal_x_source_revision(
        Session([row1, row2]), company_id=company_id, loan_id=loan_id,
    )
    b = local_principal_x_source_revision(
        Session([row2, row1]), company_id=company_id, loan_id=loan_id,
    )
    c = local_principal_x_source_revision(
        Session([row1, row2, row1]), company_id=company_id, loan_id=loan_id,
    )
    assert a == b
    assert a != c


def test_invalid_company_or_loan_scope_is_rejected():
    with pytest.raises(ValueError):
        local_principal_x_source_revision(
            Session([]), company_id="untrusted", loan_id=uuid4(),
        )
