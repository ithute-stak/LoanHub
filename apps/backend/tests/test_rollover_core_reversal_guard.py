"""All repayment reversal callers share the central rollover safety check."""
from pathlib import Path


def test_core_reversal_guard_protects_restructured_repayments():
    service = (Path(__file__).resolve().parents[3] / "apps/backend/services/loan_service.py").read_text()
    reversal = service.split("def reverse_loan_payment(", 1)[1]
    guard = reversal.index('get("installment_carry_forward_history")')
    allocation_lookup = reversal.index("db.query(PaymentAllocation)")
    assert guard < allocation_lookup
    assert "status_code=409" in reversal[:allocation_lookup]
    assert "Reverse the restructuring before reversing historical repayments" in reversal
