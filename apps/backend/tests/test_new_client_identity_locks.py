"""Phase 64 deterministic locking regression tests (no live database)."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from services.new_client_identity_locks import (
    RegistrationLockUnavailable,
    _identity_lock_keys,
    check_with_transaction_identity_locks,
)
from services.new_client_identity_guard import NewClientGuardDecision


def fake_db(dialect="postgresql", transaction=True):
    db = MagicMock()
    db.get_bind.return_value = SimpleNamespace(
        dialect=SimpleNamespace(name=dialect))
    db.in_transaction.return_value = transaction
    return db


def params(**changes):
    data = dict(company_id=uuid4(), national_id=" SYN-123 ",
                passport_number=None, phone=" 59000000 ", email="A@EXAMPLE.LS")
    data.update(changes)
    return data


def test_keys_are_normalized_sorted_and_global():
    a = _identity_lock_keys(national_id=" SYN-123 ",
                            passport_number=None, phone=" 59000000 ",
                            email="A@EXAMPLE.LS")
    b = _identity_lock_keys(national_id="syn-123",
                            passport_number=None, phone="59000000",
                            email="a@example.ls")
    assert a == b
    assert list(a) == sorted(a)
    assert len(a) == 3


def test_acquires_locks_then_checks_without_permitting_write():
    db = fake_db()
    result = NewClientGuardDecision(
        candidate=False, reason="candidate_requires_transactional_reservation",
        identity_conflicts=0, legacy_conflicts=0)
    with patch(
        "services.new_client_identity_locks.inspect_new_client_candidate",
        return_value=result,
    ) as guard:
        answer = check_with_transaction_identity_locks(db, **params())
    assert answer.candidate is False
    assert db.execute.call_count == 3
    assert guard.call_count == 1
    assert all("pg_advisory_xact_lock" in str(call.args[0])
               for call in db.execute.call_args_list)
    locked = [call.args[1]["identity_key"]
              for call in db.execute.call_args_list]
    assert locked == sorted(locked)


@pytest.mark.parametrize("dialect,transaction", [
    ("sqlite", True), ("postgresql", False), ("mysql", True),
])
def test_unsupported_db_or_missing_transaction_fails_closed(dialect, transaction):
    db = fake_db(dialect, transaction)
    with pytest.raises(RegistrationLockUnavailable):
        check_with_transaction_identity_locks(db, **params())
    db.execute.assert_not_called()


@pytest.mark.parametrize("change", [
    {"national_id": None, "passport_number": None},
    {"phone": ""},
    {"national_id": "\nBAD"},
    {"email": "A" * 151},
])
def test_invalid_identity_never_acquires_a_lock(change):
    db = fake_db()
    with pytest.raises(ValueError):
        check_with_transaction_identity_locks(db, **params(**change))
    db.execute.assert_not_called()


def test_document_type_is_in_fifth_colon_component():
    keys = _identity_lock_keys(
        national_id="NID-001", passport_number=None,
        phone="59000000", email=None,
    )
    assert "loanhub:new-client:identity:v1:national_id:nid-001" in keys
    assert all(k.split(":")[4] in ("national_id", "passport_number", "phone", "email")
               for k in keys)


def test_passport_only_identity_is_supported():
    keys = _identity_lock_keys(
        national_id=None, passport_number="PASSPORT-001",
        phone="59000000", email=None,
    )
    assert any(":passport_number:" in key for key in keys)


def test_identity_value_cannot_substitute_for_document_kind():
    with pytest.raises(ValueError):
        _identity_lock_keys(
            national_id=None, passport_number=None,
            phone="national_id", email="test@example.ls",
        )
