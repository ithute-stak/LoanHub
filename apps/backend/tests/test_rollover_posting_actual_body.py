"""Execute production rollover posting body in isolation, without opening its 503 gate.

This exercises the actual financial mutation path with substituted ORM objects,
including its real component split and accounting conservation validator.
Durable PostgreSQL service execution remains a separate certification task.
"""
import ast
import inspect
import textwrap
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import InstallmentStatus, LoanStatus
from services import final_installment_rollover_posting as service


class Query:
    def __init__(self, result):
        self.result = result
    def filter(self, *args):
        return self
    def with_for_update(self):
        return self
    def one_or_none(self):
        return self.result
    def all(self):
        return self.result


class Session:
    def __init__(self, parent):
        self.results = iter([parent, []])
        self.added = []
        self.committed = False
        self.flush_count = 0
    def query(self, *args):
        return Query(next(self.results))
    def add(self, record):
        self.added.append(record)
    def flush(self):
        self.flush_count += 1
    def commit(self):
        self.committed = True


def _isolated_posting():
    tree = ast.parse(textwrap.dedent(inspect.getsource(service.post_final_rollover)))
    function = tree.body[0]
    entry = function.body[0]
    assert isinstance(entry, ast.Raise)
    assert any(k.arg == "status_code" and isinstance(k.value, ast.Constant)
               and k.value.value == 503 for k in entry.exc.keywords)
    function.body.pop(0)
    ast.fix_missing_locations(tree)
    namespace = vars(service).copy()
    exec(compile(tree, inspect.getfile(service.post_final_rollover), "exec"), namespace)
    return namespace["post_final_rollover"]


def test_posting_body_transfers_only_unpaid_principal_without_cash(monkeypatch):
    company, parent_id, installment_id, maker = [uuid4() for _ in range(4)]
    due = date(2026, 12, 1)
    row = SimpleNamespace(id=installment_id, principal_due=Decimal("100"),
        interest_due=Decimal("0"), fee_due=Decimal("0"), total_due=Decimal("100"),
        paid_amount=Decimal("40"), status=InstallmentStatus.PARTIALLY_PAID,
        is_superseded=False, superseded_at=None)
    parent = SimpleNamespace(id=parent_id, company_id=company, parent_loan_id=None,
        cdas_collection_enabled=False, calculation_breakdown={},
        installments=[row], balance=Decimal("60"), total_repayable=Decimal("100"),
        interest_rate=Decimal("0"), status=LoanStatus.ACTIVE, is_overdue=True,
        branch_id=uuid4(), borrower_id=uuid4(), company=SimpleNamespace(),
        repayment_type=SimpleNamespace(value="monthly"), calculation_method="flat",
        preferred_payment_day=1, risk_level="low", loan_reference="OLD-LOAN")
    db = Session(parent)
    def loan(**fields):
        return SimpleNamespace(id=uuid4(), folio_number="TEST-FOLIO", **fields)
    monkeypatch.setattr(service, "ClientCompanyLoan", type("LoanFactory", (), {
        "__new__": staticmethod(lambda cls, **kwargs: loan(**kwargs)),
        "id": SimpleNamespace(__eq__=lambda self, other: True),
        "company_id": SimpleNamespace(__eq__=lambda self, other: True),
        "parent_loan_id": SimpleNamespace(__eq__=lambda self, other: True),
    }))
    monkeypatch.setattr(service, "RepaymentInstallment",
        lambda **fields: SimpleNamespace(**fields))
    monkeypatch.setattr(service, "LoanRolloverTransfer",
        lambda **fields: SimpleNamespace(**fields))
    monkeypatch.setattr(service, "AuditLog",
        lambda **fields: SimpleNamespace(**fields))
    monkeypatch.setattr(service, "prepare_linked_rollover",
        lambda *args, **kwargs: {"approved_transfer_amount": "60"})
    monkeypatch.setattr(service, "validate_rollover_receivable_transfer",
        lambda **kwargs: None)
    monkeypatch.setattr(service, "generate_loan_reference",
        lambda *args: "ROLLOVER-CHILD")
    result = _isolated_posting()(
        db, company_id=company, parent_id=parent_id, installment_id=installment_id,
        approved_amount=Decimal("60"), due_date=due,
        agreement_reference="SIGNED", approval_reference="APPROVED",
        actor_user_id=maker, actor_role="owner", as_of=date(2026, 11, 2))
    assert db.committed and db.flush_count == 2
    assert result["transferred_amount"] == "60"
    assert result["cash_disbursement"] == "0.00"
    assert parent.balance == Decimal("0") and parent.status == LoanStatus.COMPLETED
    assert parent.is_overdue is False
    assert row.paid_amount == Decimal("40") and row.is_superseded is True
    assert len(db.added) == 4
    child, installment, transfer, audit = db.added
    assert child.balance == Decimal("60") and child.principal_amount == Decimal("60")
    assert installment.principal_due == Decimal("60")
    assert transfer.transfer_amount == Decimal("60")
    assert transfer.principal_component == Decimal("60")
    assert audit.event_data["no_cash_movement"] is True
    assert parent.calculation_breakdown["linked_rollover_out"]["original"]["loan_is_overdue"] is True
    with pytest.raises(HTTPException) as error:
        service.post_final_rollover(None, company_id=company, parent_id=parent_id,
            installment_id=installment_id, approved_amount=Decimal("60"),
            due_date=due, agreement_reference="SIGNED", approval_reference="APPROVED",
            actor_user_id=maker, actor_role="owner", as_of=date(2026, 11, 2))
    assert error.value.status_code == 503
