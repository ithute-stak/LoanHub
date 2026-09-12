from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from database.models.enums import InstallmentStatus, PaymentPurpose
from services.accounting_service import _loan_repayment_components
from services.loan_service import early_settlement_required_for_payoff
from services.lelefa_paygate_service import _safe_gateway_payload


def test_settlement_accounting_uses_signed_quote_components():
    settlement_id = uuid4()
    quote = SimpleNamespace(
        settlement_principal=Decimal("800.00"),
        settlement_interest=Decimal("75.00"),
        settlement_fees=Decimal("25.00"),
    )
    db = SimpleNamespace(get=lambda model, identifier: quote if str(identifier) == str(settlement_id) else None)
    payment = SimpleNamespace(
        id=uuid4(),
        purpose=PaymentPurpose.LOAN_REPAYMENT,
        amount=Decimal("900.00"),
        provider_payload={"early_settlement_id": str(settlement_id)},
    )

    assert _loan_repayment_components(db, payment) == (
        Decimal("800.00"),
        Decimal("75.00"),
        Decimal("25.00"),
    )


def test_gateway_payload_keeps_settlement_context_but_drops_sensitive_response_fields():
    settlement_id = uuid4()
    payload = _safe_gateway_payload(
        response={
            "id": "pay_123",
            "status": "processing",
            "provider": "sandbox",
            "card_number": "4111111111111111",
            "cvv": "123",
        },
        resource_type="payment_intent",
        branch_id=None,
        internal_reference="LH-SETTLEMENT-001",
        integration_context={"early_settlement_id": str(settlement_id)},
    )

    assert payload["early_settlement_id"] == str(settlement_id)
    assert payload["gateway_public_id"] == "pay_123"
    assert payload["internal_reference"] == "LH-SETTLEMENT-001"
    assert "card_number" not in payload
    assert "cvv" not in payload



def _installment(*, due_date, status, total_due="100.00", paid_amount="0.00"):
    return SimpleNamespace(
        due_date=due_date,
        status=status,
        total_due=Decimal(total_due),
        paid_amount=Decimal(paid_amount),
        is_superseded=False,
    )


def test_paying_second_and_third_installments_together_requires_settlement_quote():
    today = date(2026, 8, 13)
    loan = SimpleNamespace(
        balance=Decimal("200.00"),
        installments=[
            _installment(
                due_date=today - timedelta(days=30),
                status=InstallmentStatus.PAID,
                paid_amount="100.00",
            ),
            _installment(due_date=today, status=InstallmentStatus.PENDING),
            _installment(
                due_date=today + timedelta(days=30),
                status=InstallmentStatus.PENDING,
            ),
        ],
    )

    required, future_count = early_settlement_required_for_payoff(
        loan,
        amount_applied=Decimal("200.00"),
        as_of_date=today,
    )

    assert required is True
    assert future_count == 1


def test_partial_advance_payment_keeps_original_agreement():
    today = date(2026, 8, 13)
    loan = SimpleNamespace(
        balance=Decimal("200.00"),
        installments=[
            _installment(due_date=today, status=InstallmentStatus.PENDING),
            _installment(
                due_date=today + timedelta(days=30),
                status=InstallmentStatus.PENDING,
            ),
        ],
    )

    required, future_count = early_settlement_required_for_payoff(
        loan,
        amount_applied=Decimal("100.00"),
        as_of_date=today,
    )

    assert required is False
    assert future_count == 0


def test_full_payment_on_final_due_date_is_normal_contract_completion():
    today = date(2026, 8, 13)
    loan = SimpleNamespace(
        balance=Decimal("100.00"),
        installments=[
            _installment(due_date=today, status=InstallmentStatus.PENDING),
        ],
    )

    required, future_count = early_settlement_required_for_payoff(
        loan,
        amount_applied=Decimal("100.00"),
        as_of_date=today,
    )

    assert required is False
    assert future_count == 0
