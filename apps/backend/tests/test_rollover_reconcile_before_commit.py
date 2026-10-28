"""Rollover service contract: accounting reconciles before transaction commit."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"services"


def test_posting_reconciles_persisted_receivables_before_commit():
    s=(ROOT/"final_installment_rollover_posting.py").read_text()
    body=s.split("def post_final_rollover(",1)[1]
    assert "transfer_record = LoanRolloverTransfer(" in body
    assert body.index("db.flush()") < body.rindex("reconcile_rollover_accounting(")
    assert body.rindex("reconcile_rollover_accounting(") < body.index("db.commit()")
    assert 'parent_before=original["balance"]' in body
    assert 'child_before=Decimal("0")' in body
    assert body.index("status_code=503") < body.index("db.query(")


def test_compensation_reconciles_reverse_movements_before_commit():
    s=(ROOT/"rollover_compensation_posting.py").read_text()
    body=s.split("def post_rollover_compensation(",1)[1]
    assert "before_parent_balance, before_child_balance = parent.balance, child.balance" in body
    assert "parent_before=before_child_balance, parent_after=child.balance" in body
    assert "child_before=before_parent_balance, child_after=parent.balance" in body
    assert body.index("db.flush()") < body.rindex("reconcile_rollover_accounting(")
    assert body.rindex("reconcile_rollover_accounting(") < body.index("db.commit()")
    assert body.index("status_code=503") < body.index("db.query(")
