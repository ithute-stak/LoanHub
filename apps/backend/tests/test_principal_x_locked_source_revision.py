"""Local state fingerprints are read-only, deterministic, and loan scoped."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from database.models.accounting import JournalEntry, JournalLine
from database.models.governance_control import PaymentAdjustment
from database.models.legacy_loan_capture import LegacyLoanCapture
from database.models.origination import LoanContract
from database.models.lelefa_paygate import LelefaPayGateWebhookEvent
from database.models.cash import CashTransaction
from database.models.payment import PaymentTransaction
from database.models.repayment import PaymentAllocation, RepaymentInstallment
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
    def __init__(self, payments, cash=(), allocations=(), treasury=(), installments=()):
        self.data = {
            PaymentTransaction: list(payments), CashTransaction: list(cash),
            PaymentAllocation: list(allocations), TreasuryEntry: list(treasury),
            RepaymentInstallment: list(installments),
        }

    def query(self, model):
        return Query(self.data.get(model, []))


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


@pytest.mark.parametrize("field,new_value", [
    ("principal_due", Decimal("98.00")),
    ("interest_due", Decimal("18.00")),
    ("fee_due", Decimal("6.00")),
    ("total_due", Decimal("122.00")),
    ("paid_amount", Decimal("50.00")),
    ("status", "paid"),
    ("due_date", "2026-12-31"),
    ("is_superseded", True),
])
def test_installment_financial_or_status_change_invalidates_revision(field, new_value):
    company_id, loan_id = uuid4(), uuid4()
    installment = SimpleNamespace(
        id=uuid4(), loan_id=loan_id,
        principal_due=Decimal("100.00"),
        interest_due=Decimal("20.00"),
        fee_due=Decimal("5.00"),
        total_due=Decimal("125.00"),
        paid_amount=Decimal("0.00"),
        status="pending", due_date="2026-12-01",
        is_superseded=False,
    )
    session = Session([], installments=[installment])
    before = local_principal_x_source_revision(
        session, company_id=company_id, loan_id=loan_id,
    )
    setattr(installment, field, new_value)
    after = local_principal_x_source_revision(
        session, company_id=company_id, loan_id=loan_id,
    )
    assert before != after


def test_installment_row_added_or_removed_invalidates_revision():
    company_id, loan_id = uuid4(), uuid4()
    session = Session([])
    before = local_principal_x_source_revision(
        session, company_id=company_id, loan_id=loan_id,
    )
    session.data[RepaymentInstallment].append(
        SimpleNamespace(id=uuid4(), loan_id=loan_id, total_due=Decimal("10.00"))
    )
    after = local_principal_x_source_revision(
        session, company_id=company_id, loan_id=loan_id,
    )
    assert before != after


@pytest.mark.parametrize("model,field,old,new", [
    (LegacyLoanCapture, "amount_paid", Decimal("100"), Decimal("101")),
    (LegacyLoanCapture, "conversion_data", {"receipt_book_total_paid": "100"}, {"receipt_book_total_paid": "101"}),
    (LoanContract, "contract_hash", "a", "b"),
    (LoanContract, "terms_snapshot", {"amount_paid_at_migration": "100"}, {"amount_paid_at_migration": "101"}),
    (PaymentAdjustment, "status", "processing", "completed"),
    (PaymentAdjustment, "amount", Decimal("100"), Decimal("101")),
    (LelefaPayGateWebhookEvent, "processing_status", "received", "processed"),
    (LelefaPayGateWebhookEvent, "payload", {"data": {"amount": "100"}}, {"data": {"amount": "101"}}),
    (JournalEntry, "status", "posted", "draft"),
    (JournalEntry, "total_credit", Decimal("100"), Decimal("101")),
    (JournalLine, "credit", Decimal("100"), Decimal("101")),
    (JournalLine, "account_id", "account-a", "account-b"),
])
def test_expanded_evidence_change_invalidates_revision(model, field, old, new):
    company_id, loan_id = uuid4(), uuid4()
    row = SimpleNamespace(id=uuid4(), **{field: old})
    session = Session([])
    session.data[model] = [row]
    before = local_principal_x_source_revision(session, company_id=company_id, loan_id=loan_id)
    setattr(row, field, new)
    after = local_principal_x_source_revision(session, company_id=company_id, loan_id=loan_id)
    assert before != after


def test_nested_json_key_order_does_not_change_revision():
    company_id, loan_id = uuid4(), uuid4()
    row = SimpleNamespace(id=uuid4(), payload={"data": {"amount": "100", "currency": "LSL"}})
    session = Session([])
    session.data[LelefaPayGateWebhookEvent] = [row]
    before = local_principal_x_source_revision(session, company_id=company_id, loan_id=loan_id)
    row.payload = {"data": {"currency": "LSL", "amount": "100"}}
    assert before == local_principal_x_source_revision(session, company_id=company_id, loan_id=loan_id)
