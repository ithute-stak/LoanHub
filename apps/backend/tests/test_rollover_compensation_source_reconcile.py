"""Contract checks for source installment reconciliation before balance restoration."""
from pathlib import Path

SERVICE=(Path(__file__).resolve().parents[1]/"services/rollover_compensation_posting.py").read_text()

def test_source_balance_reconciled_before_mutations():
    fn=SERVICE.split("def post_rollover_compensation(",1)[1]
    assert "source_remaining = Decimal(str(source.total_due)) - Decimal(str(source.paid_amount))" in fn
    assert fn.index("source_remaining =") < fn.index("parent.balance = amount")
    assert "Source installment unpaid balance no longer matches rollover transfer" in fn

def test_service_remains_disabled():
    fn=SERVICE.split("def post_rollover_compensation(",1)[1]
    assert fn.index("status_code=503") < fn.index("db.query(")
