"""Phase 36 unit tests: no financial execution or production schema changes."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest

from services.batlokoa_reservation_store import (
    ReservationDecision, ReservationError, ReservationRequest,
    reservation_table, reserve_in_existing_transaction, validate_request,
)

COMPANY = UUID("4236a21f-5164-48aa-90f3-a35eccd23ae2")
OTHER = UUID("00000000-0000-4000-8000-000000000002")
LOAN = UUID("00000000-0000-4000-8000-000000000003")
BORROWER = UUID("00000000-0000-4000-8000-000000000004")
RESERVATION = UUID("00000000-0000-4000-8000-000000000005")


def example(**changes):
    args = {
        "company_id": COMPANY,
        "loan_id": LOAN,
        "borrower_id": BORROWER,
        "idempotency_key": "collect_request_TEST123456",
        "request_fingerprint": "a" * 64,
        "amount": Decimal("100.00"),
    }
    args.update(changes)
    return ReservationRequest(**args)


def test_metadata_not_registered_in_production_base():
    from database.base import Base
    assert reservation_table.metadata is not Base.metadata
    assert reservation_table.name not in Base.metadata.tables


def test_valid_request():
    assert validate_request(example()) is None


@pytest.mark.parametrize("change", [
    {"idempotency_key": "too-short"},
    {"request_fingerprint": "unsafe"},
    {"amount": Decimal("0")},
    {"amount": Decimal("-1")},
    {"amount": Decimal("1.001")},
    {"amount": Decimal("NaN")},
    {"amount": Decimal("Infinity")},
    {"amount": Decimal("999999999999999999.99")},
    {"currency": "USD"},
    {"loan_id": "caller-controlled"},
])
def test_invalid_request_rejected(change):
    with pytest.raises(ReservationError):
        validate_request(example(**change))


class FakeResult:
    def __init__(self, item):
        self.item = item

    def scalar_one_or_none(self):
        return self.item

    def mappings(self):
        return self

    def one_or_none(self):
        return self.item


class FakeDB:
    def __init__(self, *, inserted=None, existing=None, active=True):
        self.inserted = inserted
        self.existing = existing
        self.active = active
        self.calls = []

    def in_transaction(self):
        return self.active

    def execute(self, query, params):
        sql = str(query)
        self.calls.append(sql)
        if "INSERT INTO" in sql:
            return FakeResult(self.inserted)
        assert "FOR UPDATE" in sql
        return FakeResult(self.existing)

    def commit(self):
        raise AssertionError("Store must not commit")

    def rollback(self):
        raise AssertionError("Store must not roll back")


def stored(**changes):
    row = {
        "id": RESERVATION,
        "loan_id": LOAN,
        "borrower_id": BORROWER,
        "request_fingerprint": "a" * 64,
        "amount": Decimal("100.00"),
        "currency": "LSL",
    }
    row.update(changes)
    return row


def test_disabled_store_cannot_write():
    db = FakeDB()
    with pytest.raises(ReservationError, match="disabled"):
        reserve_in_existing_transaction(db, request=example(),
                                        verified_company_id=COMPANY)
    assert not db.calls


def test_cross_company_fails_before_sql():
    db = FakeDB()
    with pytest.raises(ReservationError, match="company"):
        reserve_in_existing_transaction(db, request=example(),
                                        verified_company_id=OTHER, enabled=True)
    assert not db.calls


def test_transaction_is_required_before_sql():
    db = FakeDB(active=False)
    with pytest.raises(ReservationError, match="transaction"):
        reserve_in_existing_transaction(db, request=example(),
                                        verified_company_id=COMPANY, enabled=True)
    assert not db.calls


def test_first_request_creates_reservation_without_commit():
    db = FakeDB(inserted=RESERVATION)
    result = reserve_in_existing_transaction(
        db, request=example(), verified_company_id=COMPANY, enabled=True,
    )
    assert result.decision is ReservationDecision.CREATED
    assert result.reservation_id == RESERVATION
    assert len(db.calls) == 1
    assert "ON CONFLICT (company_id, idempotency_key) DO NOTHING" in db.calls[0]


def test_same_request_is_replay_and_locks_existing_row():
    db = FakeDB(existing=stored())
    result = reserve_in_existing_transaction(
        db, request=example(), verified_company_id=COMPANY, enabled=True,
    )
    assert result.decision is ReservationDecision.REPLAY
    assert len(db.calls) == 2
    assert "FOR UPDATE" in db.calls[1]


@pytest.mark.parametrize("change", [
    {"loan_id": OTHER},
    {"borrower_id": OTHER},
    {"request_fingerprint": "b" * 64},
    {"amount": Decimal("101.00")},
    {"currency": "USD"},
])
def test_conflicting_same_tenant_key_never_reused(change):
    db = FakeDB(existing=stored(**change))
    result = reserve_in_existing_transaction(
        db, request=example(), verified_company_id=COMPANY, enabled=True,
    )
    assert result.decision is ReservationDecision.CONFLICT


def test_missing_row_after_conflict_is_error():
    db = FakeDB()
    with pytest.raises(ReservationError, match="not found"):
        reserve_in_existing_transaction(
            db, request=example(), verified_company_id=COMPANY, enabled=True,
        )
