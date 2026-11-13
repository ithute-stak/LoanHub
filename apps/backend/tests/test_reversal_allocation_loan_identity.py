"""Reversal must fail before altering an installment from a different loan."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import PaymentPurpose
from services import loan_service


@pytest.mark.parametrize("installment_present", [True, False])
def test_cross_loan_or_missing_installment_allocation_is_rejected(
    monkeypatch, installment_present,
):
    loan_id, foreign_loan_id = uuid4(), uuid4()
    loan = SimpleNamespace(
        id=loan_id,
        calculation_breakdown={},
        amount_paid=Decimal("100.00"),
        balance=Decimal("900.00"),
        status="active",
    )
    payment = SimpleNamespace(
        id=uuid4(),
        loan_id=loan_id,
        loan=loan,
        purpose=PaymentPurpose.LOAN_REPAYMENT,
        amount=Decimal("100.00"),
        provider_payload={},
    )
    allocation = SimpleNamespace(
        payment_id=payment.id,
        installment_id=uuid4(),
        amount=Decimal("100.00"),
    )
    installment = (
        SimpleNamespace(
            id=allocation.installment_id,
            loan_id=foreign_loan_id,
            paid_amount=Decimal("100.00"),
            total_due=Decimal("100.00"),
            is_superseded=False,
        )
        if installment_present else None
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.all.return_value = [allocation]
    db.get.return_value = installment
    monkeypatch.setattr(
        "services.early_settlement_service.reverse_early_settlement",
        lambda _db, _payment: False,
    )

    with pytest.raises(HTTPException) as caught:
        loan_service.reverse_loan_payment(db, payment)

    assert caught.value.status_code == 409
    assert "reconciliation" in caught.value.detail.lower()
    assert loan.amount_paid == Decimal("100.00")
    assert loan.balance == Decimal("900.00")
    if installment is not None:
        assert installment.paid_amount == Decimal("100.00")
    db.add.assert_not_called()
    db.commit.assert_not_called()
