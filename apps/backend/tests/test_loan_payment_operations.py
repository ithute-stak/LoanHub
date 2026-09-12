from datetime import date
from pathlib import Path

from integrations.lelefa_paygate import LelefaPayGateClient
from database.schemas.loan_payment_operations import BorrowerMandateCreate


BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend"


def _client_with_capture(captured):
    client = object.__new__(LelefaPayGateClient)
    client._request = lambda method, path, **kwargs: captured.update({"method": method, "path": path, **kwargs}) or {"public_id": "mand_test", "status": "processing"}
    return client


def test_gateway_mandate_payload_contains_consent_schedule_but_no_pin():
    captured = {}
    client = _client_with_capture(captured)
    client.create_mandate(provider="mpesa", phone="+26659000000", reference="LH123", first_payment_date=date(2026,9,30), expiry_date=date(2027,9,30), metadata={"loan_id":"loan-1"}, idempotency_key="mandate-test-1")
    assert captured["path"] == "/mandates"
    body = captured["payload"]
    assert body["agreed_terms"] is True
    assert body["first_payment_date"] == "2026-09-30"
    assert "pin" not in str(body).lower()
    assert "card" not in str(body).lower()


def test_gateway_mandate_charge_uses_idempotent_protected_endpoint():
    captured = {}
    client = _client_with_capture(captured)
    client.charge_mandate("mand_test", amount="450.00", reference="LH-LOAN-1", idempotency_key="mandate-charge-1")
    assert captured["path"] == "/mandates/mand_test/charges"
    assert captured["idempotency_key"] == "mandate-charge-1"
    assert captured["payload"] == {
        "amount": "450.00",
        "currency": "LSL",
        "reference": "LH-LOAN-1",
        "check_balance_first": True,
    }


def test_automatic_debit_accepts_only_the_current_mandate_capable_rail():
    schema = BorrowerMandateCreate.model_json_schema()
    assert schema["properties"]["provider"]["const"] == "mpesa"


def test_frontend_exposes_settlement_mandates_reminders_and_restructure_controls():
    api = (FRONTEND / "api" / "lelefaPayGate.ts").read_text()
    panel = (FRONTEND / "components" / "borrower" / "borrower-online-payment-panel.tsx").read_text()
    operations = (FRONTEND / "app" / "(dashboard)" / "company" / "payment-operations" / "page.tsx").read_text()
    assert "createBorrowerSettlementQuote" in api
    assert "createBorrowerSettlementCheckout" in api
    assert "unearned_interest_rebate" in panel
    assert "Automatic repayment" in panel
    assert "Repayment reminders" in operations
    assert "Restructure requests" in operations


def test_migration_is_linear_from_early_settlement_head():
    migration = (BACKEND / "alembic" / "versions" / "f6v0x2z4a576_loan_payment_operations.py").read_text()
    assert 'down_revision: Union[str, Sequence[str], None] = "e4t8v0x2y355"' in migration
    assert "online_repayment_mandates" in migration
    assert "loan_restructure_requests" in migration
