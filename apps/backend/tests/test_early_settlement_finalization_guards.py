"""Behavioral checks for early-settlement finalization fail-closed paths.

No database writes or payment accounting side effects are performed here.
"""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import PaymentStatus
from services import early_settlement_service as service


class LockedQuery:
    def __init__(self, result):
        self.result = result
        self.locked = False

    def filter(self, *args):
        return self

    def with_for_update(self):
        self.locked = True
        return self

    def first(self):
        assert self.locked, "Settlement quote must be row-locked"
        return self.result


class FakeSession:
    def __init__(self, quote):
        self.quote = quote
        self.query_calls = 0

    def query(self, model):
        self.query_calls += 1
        return LockedQuery(self.quote)


def test_finalization_is_idempotent_when_quote_already_settled(monkeypatch):
    quote = SimpleNamespace(id=uuid4(), status="settled")
    db = FakeSession(quote)
    payment = SimpleNamespace(status=PaymentStatus.SUCCEEDED)
    monkeypatch.setattr(service, "_quote_from_payment", lambda db, payment: quote)
    assert service.finalize_early_settlement_payment(db, payment) is quote
    assert service.finalize_early_settlement_payment(db, payment) is quote
    assert db.query_calls == 2
    assert quote.status == "settled"


@pytest.mark.parametrize("status", [PaymentStatus.FAILED, PaymentStatus.PENDING])
def test_finalization_rejects_unconfirmed_payment_before_loan_mutation(monkeypatch, status):
    quote = SimpleNamespace(id=uuid4(), status="processing")
    db = FakeSession(quote)
    payment = SimpleNamespace(status=status, amount=Decimal("100.00"))
    monkeypatch.setattr(service, "_quote_from_payment", lambda db, payment: quote)
    with pytest.raises(HTTPException) as error:
        service.finalize_early_settlement_payment(db, payment)
    assert error.value.status_code == 409
    assert db.query_calls == 1
    assert quote.status == "processing"
