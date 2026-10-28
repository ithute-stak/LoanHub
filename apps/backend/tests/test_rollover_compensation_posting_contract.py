"""Proposed compensation moves balances without changing historical payments."""
from pathlib import Path

SERVICE=(Path(__file__).resolve().parents[1]/"services/rollover_compensation_posting.py").read_text()

def test_compensation_remains_disabled_at_entry():
    body=SERVICE.split("def post_rollover_compensation(",1)[1]
    assert body.index("status_code=503") < body.index("db.query(")

def test_proposed_compensation_writes_one_ledger_and_commit():
    body=SERVICE.split("def post_rollover_compensation(",1)[1]
    assert "parent.balance = amount" in body
    assert 'child.balance = Decimal("0")' in body
    assert "db.add(LoanRolloverCompensation(" in body
    assert body.index("db.add(LoanRolloverCompensation(") < body.index("db.commit()")
    assert body.count("db.commit()") == 1
    assert "PaymentAllocation(" not in body
    assert "PaymentTransaction(" not in body

def test_original_schedule_is_restored_and_child_schedule_closed():
    assert "source.is_superseded = False" in SERVICE
    assert "child_installment.is_superseded = True" in SERVICE
    assert "source.paid_amount =" not in SERVICE
