"""Compensation preconditions must complete before any ORM balance changes."""
from pathlib import Path

SERVICE=(Path(__file__).resolve().parents[1]/"services/rollover_compensation_posting.py").read_text()


def test_original_installment_is_locked_and_checked_before_balance_mutations():
    body=SERVICE.split("def post_rollover_compensation(",1)[1]
    assert body.index("source = db.query(RepaymentInstallment)") < body.index("parent.balance = amount")
    assert body.index("source is None or not source.is_superseded") < body.index("parent.balance = amount")
    assert body.index("source = db.query(RepaymentInstallment)") < body.index('child.balance = Decimal("0")')


def test_entrypoint_still_refuses_financial_mutation():
    body=SERVICE.split("def post_rollover_compensation(",1)[1]
    assert body.index("status_code=503") < body.index("db.query(")
    assert body.index("status_code=503") < body.index("parent.balance = amount")
