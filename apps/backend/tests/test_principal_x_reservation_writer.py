from decimal import Decimal
from uuid import uuid4

import pytest

from services.principal_x_reservation_writer import (
    bind_principal_x_payment, reserve_principal_x_collection,
)


class FakeSession:
    def __init__(self, dialect="postgresql"):
        self.dialect = dialect
        self.added = []
        self.flushes = 0

    def get_bind(self):
        class Bind:
            pass
        bind = Bind()
        bind.dialect = type("Dialect", (), {"name": self.dialect})()
        return bind

    def add(self, item):
        self.added.append(item)

    def flush(self):
        self.flushes += 1


def reserve(db, **kwargs):
    args = dict(
        company_id=uuid4(), loan_id=uuid4(), amount=Decimal("100"),
        idempotency_key="idem-1", provider_reference="provider-1",
    )
    args.update(kwargs)
    return reserve_principal_x_collection(db, **args)


def test_writer_flushes_without_committing():
    db = FakeSession()
    row = reserve(db)
    assert db.added == [row]
    assert db.flushes == 1
    assert row.amount == Decimal("100.00")
    assert row.payment_transaction_id is None


@pytest.mark.parametrize("changed", [
    {"amount": Decimal("0")},
    {"amount": Decimal("NaN")},
    {"idempotency_key": ""},
    {"provider_reference": ""},
    {"idempotency_key": "x" * 256},
    {"provider_reference": "x" * 181},
    {"company_id": "not-uuid"},
])
def test_invalid_reservations_never_write(changed):
    db = FakeSession()
    with pytest.raises(ValueError):
        reserve(db, **changed)
    assert db.added == []
    assert db.flushes == 0


def test_requires_postgresql():
    db = FakeSession(dialect="sqlite")
    with pytest.raises(ValueError, match="PostgreSQL"):
        reserve(db)
    assert db.added == []


def test_payment_binding_is_write_once():
    db = FakeSession()
    row = reserve(db)
    payment_id = uuid4()
    bind_principal_x_payment(db, reservation=row, payment_transaction_id=payment_id)
    assert row.payment_transaction_id == payment_id
    assert db.flushes == 2
    with pytest.raises(ValueError, match="already bound"):
        bind_principal_x_payment(db, reservation=row, payment_transaction_id=uuid4())


def test_flush_failure_is_not_swallowed():
    class RejectingSession(FakeSession):
        def flush(self):
            raise RuntimeError("unique constraint failure")

    db = RejectingSession()
    with pytest.raises(RuntimeError, match="unique constraint"):
        reserve(db)
