from pathlib import Path

SERVICE = (Path(__file__).resolve().parents[1] / "services/rollover_compensation_posting.py").read_text()

def test_child_payment_evidence_check_present():
    assert "PaymentTransaction.loan_id == child.id" in SERVICE
    assert "PaymentTransaction.company_id == company_id" in SERVICE
    assert "RepaymentInstallment.loan_id == child.id" in SERVICE
    assert "child_payments_count=child_payment_count + allocation_count" in SERVICE

def test_compensation_remains_disabled():
    body = SERVICE.split("def post_rollover_compensation(", 1)[1]
    assert body.index("status_code=503") < body.index("db.query(")
