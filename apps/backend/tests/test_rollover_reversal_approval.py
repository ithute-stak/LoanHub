"""Maker-checker reversal decision records must fail closed."""
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects.postgresql import dialect
from database.models.loan_rollover_reversal_approval import LoanRolloverReversalApproval
from services import rollover_reversal_approval as approval


class Query:
    def __init__(self, decision):
        self.decision = decision
    def filter(self, *args):
        return self
    def one_or_none(self):
        return self.decision


class DB:
    def __init__(self, decision):
        self.decision = decision
    def query(self, *args):
        return Query(self.decision)


def test_missing_approval_rejected(monkeypatch):
    monkeypatch.setattr(approval, "verify_rollover_checker_identity", lambda *a, **kw: pytest.fail("No checker lookup without decision"))
    with pytest.raises(HTTPException) as error:
        approval.require_rollover_reversal_approval(
            DB(None), company_id=uuid4(), transfer_id=uuid4(),
            maker_user_id=uuid4(), checker_user_id=uuid4(),
            approval_reference="TEST",
        )
    assert error.value.status_code == 409


def test_approved_decision_still_checks_current_checker_authorization(monkeypatch):
    expected = SimpleNamespace(id=uuid4())
    called = []
    monkeypatch.setattr(approval, "verify_rollover_checker_identity", lambda *a, **kw: called.append(kw))
    result = approval.require_rollover_reversal_approval(
        DB(expected), company_id=uuid4(), transfer_id=uuid4(),
        maker_user_id=uuid4(), checker_user_id=uuid4(),
        approval_reference="TEST",
    )
    assert result is expected
    assert len(called) == 1


def test_approval_ddl_enforces_uniqueness_independence_and_decision():
    ddl = str(CreateTable(LoanRolloverReversalApproval.__table__).compile(dialect=dialect()))
    assert "uq_rollover_reversal_approval_transfer" in ddl
    assert "ck_rollover_reversal_independent" in ddl
    assert "ck_rollover_reversal_decision" in ddl
    service = (Path(__file__).resolve().parents[1] / "services/rollover_compensation_posting.py").read_text()
    body = service.split("def post_rollover_compensation(", 1)[1]
    assert body.index("status_code=503") < body.index("require_rollover_reversal_approval(")
    assert body.index("require_rollover_reversal_approval(") < body.index("parent.balance = amount")
