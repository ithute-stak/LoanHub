"""Execute the real compensation body with isolated in-memory ORM substitutes.

The public 503 entrypoint is never modified. Unlike static ordering tests, this
executes the entire authorized compensation body including actual preflight,
history validation, balance changes and accounting reconciliation. Database
persistence is a separate outstanding PostgreSQL certification requirement.
"""
import ast
import inspect
import textwrap
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import InstallmentStatus, LoanStatus
from services import rollover_compensation_posting as module


class Query:
    def __init__(self, value):
        self.value = value
    def filter(self, *args):
        return self
    def with_for_update(self):
        return self
    def join(self, *args):
        return self
    def one_or_none(self):
        return self.value
    def first(self):
        return self.value
    def all(self):
        return self.value
    def count(self):
        return self.value


class DB:
    def __init__(self, results):
        self.results = iter(results)
        self.writes = []
        self.committed = False
    def query(self, *args):
        return Query(next(self.results))
    def add(self, record):
        self.writes.append(record)
    def flush(self):
        pass
    def commit(self):
        self.committed = True


def _test_only_compensation():
    tree = ast.parse(textwrap.dedent(inspect.getsource(module.post_rollover_compensation)))
    fn = tree.body[0]
    gate = fn.body[0]
    assert isinstance(gate, ast.Raise)
    assert any(keyword.arg == "status_code" and isinstance(keyword.value, ast.Constant)
               and keyword.value.value == 503 for keyword in gate.exc.keywords)
    fn.body.pop(0)
    ast.fix_missing_locations(tree)
    namespace = vars(module).copy()
    exec(compile(tree, inspect.getfile(module.post_rollover_compensation), "exec"), namespace)
    return namespace["post_rollover_compensation"]


def test_actual_compensation_body_restores_balances_and_original_history(monkeypatch):
    company, maker, checker, parent_id, child_id, transfer_id, source_id = [uuid4() for _ in range(7)]
    original = dict(balance="60", installment_total_due="100",
                    installment_paid_amount="40", installment_principal_due="100",
                    installment_interest_due="0", installment_fee_due="0",
                    installment_status="overdue", loan_status="active",
                    loan_is_overdue=True)
    parent = SimpleNamespace(id=parent_id, company_id=company, balance=Decimal("0"),
        parent_loan_id=None, status=LoanStatus.COMPLETED, is_overdue=False,
        calculation_breakdown={"linked_rollover_out": {
            "child_loan_id": str(child_id), "amount": "60", "original": original}})
    child = SimpleNamespace(id=child_id, company_id=company, parent_loan_id=parent_id,
        balance=Decimal("60"), amount_paid=Decimal("0"), status=LoanStatus.ACTIVE,
        is_overdue=False)
    transfer = SimpleNamespace(id=transfer_id, company_id=company, parent_loan_id=parent_id,
        child_loan_id=child_id, source_installment_id=source_id, status="posted",
        transfer_amount=Decimal("60"), principal_component=Decimal("60"),
        interest_component=Decimal("0"), fee_component=Decimal("0"))
    source = SimpleNamespace(id=source_id, loan_id=parent_id, is_superseded=True,
        superseded_at="previous", total_due=Decimal("100"), paid_amount=Decimal("40"),
        principal_due=Decimal("100"), interest_due=Decimal("0"),
        fee_due=Decimal("0"), status=InstallmentStatus.OVERDUE)
    installment = SimpleNamespace(is_superseded=False, paid_amount=Decimal("0"),
        total_due=Decimal("60"), principal_due=Decimal("60"),
        interest_due=Decimal("0"), fee_due=Decimal("0"), superseded_at=None)
    # Actual service query order, with independent responses for each query.
    db = DB([transfer, None, parent, child, None, [installment], 0, 0, source])
    approved = []
    monkeypatch.setattr(module, "require_rollover_reversal_approval",
                        lambda *args, **kwargs: approved.append(kwargs))
    # The separate test compilation captures this patched approval dependency.
    result = _test_only_compensation()(db, company_id=company, transfer_id=transfer_id,
        actor_user_id=maker, independent_approver_id=checker,
        reference="COMP-TEST", approval_reference="APPROVED", reason="Test authorized reversal")
    assert len(approved) == 1
    assert db.committed
    assert result["parent_balance"] == "60"
    assert result["child_balance"] == "0"
    assert parent.balance == Decimal("60") and parent.is_overdue is True
    assert parent.status == LoanStatus.ACTIVE
    assert child.balance == Decimal("0") and child.status == LoanStatus.CANCELLED
    assert source.status == InstallmentStatus.OVERDUE
    assert source.is_superseded is False and source.paid_amount == Decimal("40")
    assert installment.is_superseded is True
    assert len(db.writes) == 1
    compensation = db.writes[0]
    assert compensation.amount == Decimal("60")
    assert compensation.transfer_id == transfer_id
    # The public endpoint must remain unavailable even after test execution.
    with pytest.raises(HTTPException) as err:
        module.post_rollover_compensation(None, company_id=company, transfer_id=transfer_id,
            actor_user_id=maker, independent_approver_id=checker, reference="X",
            approval_reference="Y", reason="Z")
    assert err.value.status_code == 503
