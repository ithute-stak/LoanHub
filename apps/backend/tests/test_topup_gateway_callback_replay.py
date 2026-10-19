"""Exercise provider callback replay controls with lightweight database stand-ins."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import PaymentStatus
from services.lelefa_paygate_service import apply_gateway_resource, _finalize_top_up


class Query:
    def filter(self, *_args):
        return self

    def first(self):
        return SimpleNamespace(status="reversed")


class Db:
    def query(self, _model):
        return Query()


def test_out_of_order_gateway_success_after_reversal_is_rejected():
    payment = SimpleNamespace(
        status=PaymentStatus.REVERSED,
        provider_reference="LPG-123",
        provider_payload={},
    )
    with pytest.raises(HTTPException) as exc:
        apply_gateway_resource(Db(), payment, {"status": "succeeded", "public_id": "LPG-123"})
    assert exc.value.status_code == 409
    assert payment.status == PaymentStatus.REVERSED


def test_existing_reversed_topup_settlement_cannot_be_replayed_as_new():
    loan = SimpleNamespace(id=uuid4(), is_top_up=True)
    payment = SimpleNamespace(loan=loan)
    with pytest.raises(HTTPException) as exc:
        _finalize_top_up(Db(), payment)
    assert exc.value.status_code == 409
    assert "settlement record" in str(exc.value.detail)
