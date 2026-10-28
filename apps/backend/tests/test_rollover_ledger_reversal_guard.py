"""Contract tests protecting historical payments after a ledger-backed rollover."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = (ROOT / "services/loan_service.py").read_text()


def test_repayment_reversal_checks_durable_rollover_ledger_before_allocations():
    reversal = SERVICE.split("def reverse_loan_payment(", 1)[1]
    ledger = reversal.index("LoanRolloverTransfer.parent_loan_id == loan.id")
    allocations = reversal.index("db.query(PaymentAllocation)")
    assert ledger < allocations
    assert "posted linked rollover exists" in reversal


def test_reversal_does_not_delete_or_rewrite_transfer_history():
    reversal = SERVICE.split("def reverse_loan_payment(", 1)[1]
    assert "db.delete(LoanRolloverTransfer" not in reversal
    assert "db.query(LoanRolloverTransfer).delete" not in reversal
