"""Regression contracts for linked descendant protection during compensation."""
from pathlib import Path

SERVICE = (Path(__file__).resolve().parents[1] / "services/rollover_compensation_posting.py").read_text()


def test_descendants_are_checked_before_schedule_and_balance_changes():
    body = SERVICE.split("def post_rollover_compensation(", 1)[1]
    assert "ClientCompanyLoan.parent_loan_id == child.id" in body
    assert "ClientCompanyLoan.company_id == company_id" in body
    assert body.index("linked_descendant = db.query(") < body.index("installments = db.query(")
    assert body.index("linked_descendant = db.query(") < body.index("parent.balance = amount")
    assert "Child loan has a linked descendant; specialist settlement required" in body


def test_unsafe_financial_operation_remains_disabled():
    body = SERVICE.split("def post_rollover_compensation(", 1)[1]
    assert body.index("status_code=503") < body.index("linked_descendant = db.query(")
