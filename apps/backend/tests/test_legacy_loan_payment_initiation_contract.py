"""Contract checks: prevent new locked-legacy payment attempts, preserve replay."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASH = (ROOT / "services" / "payment_service.py").read_text()
GATEWAY = (ROOT / "services" / "lelefa_paygate_service.py").read_text()


def test_cash_new_payment_guard_after_idempotency_replay():
    function = CASH.split("def initiate_payment(", 1)[1].split("\ndef apply_callback(", 1)[0]
    replay = function.index("if existing:\n        return existing")
    guard = function.index("is_legacy_loan_locked(db, loan.company_id, loan.id)")
    new_posting = function.index("transaction = PaymentTransaction(")
    assert replay < guard < new_posting
    assert "if loan_id:" in function


def test_gateway_guard_before_provider_interaction_and_after_replay():
    function = GATEWAY.split("def initiate_gateway_payment(", 1)[1]
    replay = function.index("if existing:\n        return existing")
    guard = function.index("is_legacy_loan_locked(db, loan.company_id, loan.id)")
    provider = function.index("client = LelefaPayGateClient()")
    assert replay < guard < provider
    assert "if loan_id:" in function


def test_gateway_finalization_is_not_new_payment_guarded():
    function = GATEWAY.split("def finalize_gateway_payment(", 1)[1].split("\ndef initiate_gateway_payment(", 1)[0]
    assert "is_legacy_loan_locked" not in function
