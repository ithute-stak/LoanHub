from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

import services.loan_last_payment_reversal as reversal
from database.models.enums import PaymentDirection, PaymentMethod, PaymentPurpose, PaymentStatus


def fixture():
    company_id, loan_id, payment_id = uuid4(), uuid4(), uuid4()
    loan = SimpleNamespace(
        id=loan_id, company_id=company_id, branch_id=uuid4(),
        amount_paid=Decimal("1200"), balance=Decimal("192"),
        cdas_collection_enabled=False,
    )
    payment = SimpleNamespace(
        id=payment_id, company_id=company_id, loan_id=loan_id,
        status=PaymentStatus.SUCCEEDED, purpose=PaymentPurpose.LOAN_REPAYMENT,
        payment_method=PaymentMethod.CASH, direction=PaymentDirection.INBOUND,
        provider_payload={}, amount=Decimal("272"),
        provider_reference="CIN-TEST", completed_at=None,
    )
    treasury = SimpleNamespace(id=uuid4(), is_voided=False)
    db = MagicMock()
    db.query.return_value.filter.return_value.with_for_update.return_value.first.side_effect = [
        loan, payment, treasury,
    ]
    return db, loan, payment, treasury


def test_reversal_requires_a_specific_reason():
    db, loan, payment, _ = fixture()
    with pytest.raises(HTTPException) as exc:
        reversal.reverse_latest_cash_repayment(
            db, loan_id=loan.id, company_id=loan.company_id,
            payment_id=payment.id, user_id=uuid4(), actor_role="company_owner",
            reason="mistake",
        )
    assert exc.value.status_code == 422
    db.commit.assert_not_called()


def test_success_reverses_ledger_and_preserves_payment_record(monkeypatch):
    db, loan, payment, treasury = fixture()
    monkeypatch.setattr(reversal, "_last_payment_query", lambda db, loan: SimpleNamespace(first=lambda: payment))
    calls = []

    def change_loan(db, payment):
        calls.append("allocations")
        loan.balance += payment.amount
        loan.amount_paid -= payment.amount

    monkeypatch.setattr(reversal, "reverse_loan_payment", change_loan)
    monkeypatch.setattr(reversal, "void_treasury_entry", lambda *args, **kwargs: calls.append("treasury"))
    monkeypatch.setattr(reversal, "record_reversal_accounting", lambda *args: calls.append("accounting") or object())

    result = reversal.reverse_latest_cash_repayment(
        db, loan_id=loan.id, company_id=loan.company_id,
        payment_id=payment.id, user_id=uuid4(), actor_role="company_owner",
        reason="Duplicate cash payment was entered",
    )
    assert result["status"] == "reversed"
    assert payment.status == PaymentStatus.REVERSED
    assert loan.balance == Decimal("464")
    assert calls == ["allocations", "treasury", "accounting"]
    assert payment.provider_payload["reversal"]["reason"] == "Duplicate cash payment was entered"
    db.commit.assert_called_once()


def test_reversal_rejects_non_cash_repayments(monkeypatch):
    db, loan, payment, treasury = fixture()
    payment.payment_method = PaymentMethod.LELEFAPAYGATE
    monkeypatch.setattr(reversal, "_last_payment_query", lambda db, loan: SimpleNamespace(first=lambda: payment))
    with pytest.raises(HTTPException) as exc:
        reversal.reverse_latest_cash_repayment(
            db, loan_id=loan.id, company_id=loan.company_id,
            payment_id=payment.id, user_id=uuid4(), actor_role="company_owner",
            reason="Duplicate gateway payment was entered",
        )
    assert exc.value.status_code == 409
    db.commit.assert_not_called()


def test_double_submission_is_idempotent():
    db, loan, payment, treasury = fixture()
    payment.status = PaymentStatus.REVERSED
    result = reversal.reverse_latest_cash_repayment(
        db, loan_id=loan.id, company_id=loan.company_id,
        payment_id=payment.id, user_id=uuid4(), actor_role="company_owner",
        reason="Duplicate cash payment was entered",
    )
    assert result["idempotent_replay"] is True
    db.commit.assert_not_called()
