from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from database.models.enums import LoanStatus, PaymentMethod
from integrations.lelefa_paygate import LelefaPayGateClient
import services.early_settlement_service as early_settlement_service
import services.lelefa_paygate_service as gateway_service
import services.loan_service as loan_service


BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend"


def _client_with_capture(captured):
    client = object.__new__(LelefaPayGateClient)

    def request(method, path, *, payload=None, idempotency_key=None):
        captured.update({
            "method": method,
            "path": path,
            "payload": payload,
            "idempotency_key": idempotency_key,
        })
        return {"public_id": "pi_test", "status": "processing"}

    client._request = request
    return client


def test_selected_provider_is_sent_to_gateway_payment_intent():
    captured = {}
    client = _client_with_capture(captured)

    client.create_payment_intent(
        amount="25.00",
        phone="+263771234567",
        reference="LOAN-1",
        metadata={"loanhub_payment_id": "payment-1"},
        idempotency_key="gateway-provider-test-1",
        provider="ecocash",
    )

    assert captured["path"] == "/payment-intents"
    assert captured["payload"]["provider"] == "ecocash"
    assert captured["payload"]["payment_method"] == "mobile_money"
    assert captured["payload"]["customer"] == {"phone": "+263771234567"}
    assert "pin" not in captured["payload"]
    assert "card" not in captured["payload"]


def test_hosted_checkout_contains_return_urls_but_no_sensitive_payment_fields(monkeypatch):
    captured = {}
    client = _client_with_capture(captured)
    # This is a low-level payload-shape test. Tenant/database routing is covered
    # separately by the PayBridge company-shortcode contract tests, so stub the
    # trusted server-side resolver here rather than weakening production routing.
    monkeypatch.setattr(
        "integrations.lelefa_paygate._company_business_shortcode",
        lambda metadata: "123456",
    )

    client.create_checkout_session(
        amount="120.00",
        reference="LOAN-ONLINE-1",
        description="Loan repayment",
        metadata={"loanhub_payment_id": "payment-2"},
        idempotency_key="gateway-checkout-test-1",
        success_url="https://loanhub.example/borrower/payments?checkout=success",
        cancel_url="https://loanhub.example/borrower/payments?checkout=cancelled",
    )

    assert captured["path"] == "/checkout-sessions"
    assert captured["payload"]["success_url"].endswith("checkout=success")
    assert captured["payload"]["business_shortcode"] == "123456"
    serialized = str(captured["payload"]).lower()
    assert "card_number" not in serialized
    assert "cvv" not in serialized
    assert "pin" not in serialized


def test_repayment_engine_forwards_provider_and_customer_phone(monkeypatch):
    loan = SimpleNamespace(
        id=uuid4(),
        company_id=uuid4(),
        borrower_id=uuid4(),
        loan_request_id=uuid4(),
        branch_id=uuid4(),
        loan_reference="LB-PROVIDER-TEST",
        status=LoanStatus.ACTIVE,
    )
    preview = {
        "amount_applied": Decimal("75.00"),
        "early_settlement_required": False,
        "future_installments_in_payoff": 0,
    }
    captured = {}

    monkeypatch.setattr(loan_service, "preview_cash_repayment", lambda *args, **kwargs: preview)
    monkeypatch.setattr(loan_service, "_existing_payment", lambda *args, **kwargs: None)
    monkeypatch.setattr(early_settlement_service, "assert_no_settlement_in_progress", lambda *args: None)

    def initiate(db, **kwargs):
        captured.update(kwargs)
        return "gateway-payment"

    monkeypatch.setattr(gateway_service, "initiate_gateway_loan_repayment", initiate)

    payment, cash, result_preview = loan_service.record_cash_repayment(
        object(),
        loan=loan,
        amount_tendered=Decimal("75.00"),
        overpayment_action="carry_forward",
        installment_number=1,
        initiated_by_user_id=uuid4(),
        payment_method=PaymentMethod.LELEFAPAYGATE,
        gateway_provider="mpesa",
        gateway_customer_phone="+26659000000",
        idempotency_key="repayment-provider-test-1",
    )

    assert payment == "gateway-payment"
    assert cash is None
    assert result_preview is preview
    assert captured["gateway_provider"] == "mpesa"
    assert captured["payer_phone"] == "+26659000000"


def test_frontend_discovers_rails_and_keeps_sensitive_fields_hosted():
    picker = (FRONTEND / "components" / "payments" / "payment-method-fields.tsx").read_text()
    borrower = (FRONTEND / "components" / "borrower" / "borrower-online-payment-panel.tsx").read_text()

    assert "getGatewayPaymentMethods" in picker
    assert "gateway_customer_phone" in picker
    assert "Never ask for or record their PIN" in picker
    assert "createBorrowerGatewayCheckout" in borrower
    assert "window.location.assign(checkout.checkout_url)" in borrower
    assert "card details" in borrower.lower()
