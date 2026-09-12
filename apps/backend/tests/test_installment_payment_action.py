from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import InstallmentStatus, LoanStatus, PaymentMethod
import services.loan_service as loan_service


def _installment(number: int, *, total: str = "696.00", paid: str = "0.00", status=InstallmentStatus.PENDING):
    return SimpleNamespace(
        id=uuid4(),
        installment_number=number,
        total_due=Decimal(total),
        paid_amount=Decimal(paid),
        status=status,
    )


def _loan():
    first = _installment(1)
    second = _installment(2)
    return SimpleNamespace(
        id=uuid4(),
        status=LoanStatus.ACTIVE,
        installments=[first, second],
    )


def test_current_installment_payment_reuses_authoritative_repayment_engine(monkeypatch):
    loan = _loan()
    first = loan.installments[0]
    captured = {}

    def fake_record(db, **kwargs):
        captured.update(kwargs)
        return "payment", "cash", {"amount_applied": Decimal("300.00")}

    monkeypatch.setattr(loan_service, "record_cash_repayment", fake_record)

    result = loan_service.record_installment_repayment(
        object(),
        loan=loan,
        installment_id=first.id,
        amount_tendered=Decimal("300.00"),
        initiated_by_user_id=uuid4(),
        payment_method=PaymentMethod.CASH,
        idempotency_key="installment-payment-test-0001",
    )

    assert result[0] == "payment"
    assert captured["installment_number"] == 1
    assert captured["amount_tendered"] == Decimal("300.00")
    assert captured["overpayment_action"] == "carry_forward"


def test_future_installment_cannot_be_paid_before_oldest_open_installment():
    loan = _loan()
    second = loan.installments[1]

    with pytest.raises(HTTPException) as caught:
        loan_service.record_installment_repayment(
            object(),
            loan=loan,
            installment_id=second.id,
            amount_tendered=Decimal("100.00"),
            initiated_by_user_id=uuid4(),
        )

    assert caught.value.status_code == 409
    assert "Installment 1" in caught.value.detail


def test_row_action_rejects_overpayment_and_keeps_advance_payment_on_payment_desk():
    loan = _loan()
    first = loan.installments[0]

    with pytest.raises(HTTPException) as caught:
        loan_service.record_installment_repayment(
            object(),
            loan=loan,
            installment_id=first.id,
            amount_tendered=Decimal("700.00"),
            initiated_by_user_id=uuid4(),
        )

    assert caught.value.status_code == 422
    assert "696.00" in caught.value.detail
    assert "payment desk" in caught.value.detail.lower()


def test_paid_installment_is_locked():
    loan = _loan()
    first = loan.installments[0]
    first.status = InstallmentStatus.PAID
    first.paid_amount = Decimal("696.00")

    with pytest.raises(HTTPException) as caught:
        loan_service.record_installment_repayment(
            object(),
            loan=loan,
            installment_id=first.id,
            amount_tendered=Decimal("1.00"),
            initiated_by_user_id=uuid4(),
        )

    assert caught.value.status_code == 409
    assert "already settled" in caught.value.detail.lower()
