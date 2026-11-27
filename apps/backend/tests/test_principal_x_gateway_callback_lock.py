"""Regression tests for repayment callback serialization and terminal states."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services import lelefa_paygate_service as gateway
from services import principal_x_financial_lock as financial_lock
from database.models.enums import PaymentPurpose, PaymentStatus


def payment(settlement_id=None):
    return SimpleNamespace(
        company_id=uuid4(), loan_id=uuid4(),
        purpose=PaymentPurpose.LOAN_REPAYMENT,
        provider_payload={"early_settlement_id": settlement_id} if settlement_id else {},
        provider_reference="gateway-123", status=PaymentStatus.PROCESSING,
    )


@pytest.mark.parametrize("settlement_id", [None, str(uuid4())])
def test_callback_acquires_loan_lock_before_refresh(monkeypatch, settlement_id):
    row = payment(settlement_id)
    calls = []
    db = SimpleNamespace(refresh=lambda value: calls.append(("refresh", value)))
    monkeypatch.setattr(financial_lock, "lock_financial_loan",
                        lambda db, **scope: calls.append(("lock", scope)))
    gateway._lock_gateway_repayment(db, row)
    assert calls == [
        ("lock", {"company_id": row.company_id, "loan_id": row.loan_id}),
        ("refresh", row),
    ]


@pytest.mark.parametrize("field", ["company_id", "loan_id", "purpose", "settlement"])
def test_changed_payment_scope_rejected_after_refresh(monkeypatch, field):
    row = payment()
    monkeypatch.setattr(financial_lock, "lock_financial_loan", lambda *a, **kw: None)
    def refresh(value):
        if field == "settlement":
            value.provider_payload = {"early_settlement_id": str(uuid4())}
        elif field == "purpose":
            value.purpose = PaymentPurpose.LOAN_DISBURSEMENT
        else:
            setattr(value, field, uuid4())
    with pytest.raises(HTTPException) as caught:
        gateway._lock_gateway_repayment(SimpleNamespace(refresh=refresh), row)
    assert caught.value.status_code == 409


@pytest.mark.parametrize("settlement_id", [None, str(uuid4())])
@pytest.mark.parametrize("incoming", ["processing", "failed", "cancelled", "reversed", "succeeded"])
def test_delayed_callback_cannot_reopen_reversed_payment(monkeypatch, settlement_id, incoming):
    row = payment(settlement_id)
    monkeypatch.setattr(financial_lock, "lock_financial_loan", lambda *a, **kw: None)
    def refresh(value):
        value.status = PaymentStatus.REVERSED
    db = SimpleNamespace(refresh=refresh)
    # No add/flush/commit methods: these branches must never write.
    if incoming == "succeeded":
        with pytest.raises(HTTPException) as caught:
            gateway.apply_gateway_resource(db, row, {"status": incoming})
        assert caught.value.status_code == 409
    else:
        assert gateway.apply_gateway_resource(db, row, {"status": incoming}) is row
    assert row.status == PaymentStatus.REVERSED
