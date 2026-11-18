"""Phase 69 idempotency tests: replay binding and no client creation."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from services.new_only_client_registration import NewOnlyRegistrationIntent
from services.new_client_registration_idempotency import (
    IdempotencyConflict, IdempotencyUnavailable,
    finalize_new_client_registration, reserve_new_client_registration,
)


def make_intent(**changes):
    data = {
        "company_id": uuid4(),
        "branch_id": uuid4(),
        "employee_id": uuid4(),
        "idempotency_key": "synthetic-request-0000001",
        "registration_fingerprint": "a" * 64,
    }
    data.update(changes)
    return NewOnlyRegistrationIntent(**data)


def database(intent, *, existing=False, mismatch=None):
    db = MagicMock()
    db.get_bind.return_value = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"))
    db.in_transaction.return_value = True
    row = SimpleNamespace(
        id=uuid4(), company_id=intent.company_id,
        branch_id=intent.branch_id,
        employee_user_id=intent.employee_id,
        idempotency_key=intent.idempotency_key,
        request_fingerprint=intent.registration_fingerprint,
        status="reserved", client_account_id=None,
    )
    if mismatch:
        setattr(row, mismatch[0], mismatch[1])
    db.execute.side_effect = [
        SimpleNamespace(scalar_one_or_none=lambda: None if existing else uuid4()),
        SimpleNamespace(scalar_one=lambda: row),
    ]
    return db, row


def test_first_request_records_reservation_without_commit():
    intent = make_intent()
    db, row = database(intent)
    result = reserve_new_client_registration(db, intent=intent)
    assert result.attempt_id == row.id
    assert result.existing is False
    assert result.status == "reserved"
    assert db.execute.call_count == 2
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_exact_replay_detected_without_creating_second_intent():
    intent = make_intent()
    db, row = database(intent, existing=True)
    result = reserve_new_client_registration(db, intent=intent)
    assert result.existing is True
    assert result.attempt_id == row.id
    db.commit.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("request_fingerprint", "b" * 64),
    ("branch_id", uuid4()),
    ("employee_user_id", uuid4()),
])
def test_conflicting_replay_fails_closed(field, value):
    intent = make_intent()
    db, _ = database(intent, existing=True, mismatch=(field, value))
    with pytest.raises(IdempotencyConflict):
        reserve_new_client_registration(db, intent=intent)
    db.commit.assert_not_called()


def test_no_non_postgres_fallback():
    intent = make_intent()
    db, _ = database(intent)
    db.get_bind.return_value.dialect.name = "sqlite"
    with pytest.raises(IdempotencyUnavailable):
        reserve_new_client_registration(db, intent=intent)
    db.execute.assert_not_called()


def test_caller_must_own_transaction():
    intent = make_intent()
    db, _ = database(intent)
    db.in_transaction.return_value = False
    with pytest.raises(IdempotencyUnavailable):
        reserve_new_client_registration(db, intent=intent)
    db.execute.assert_not_called()


def test_completion_always_disabled_until_safe_create_exists():
    intent = make_intent()
    db = MagicMock()
    with pytest.raises(IdempotencyUnavailable):
        finalize_new_client_registration(
            db, intent=intent, reservation=None,
            client_account_id=uuid4())
    db.commit.assert_not_called()
    db.add.assert_not_called()
