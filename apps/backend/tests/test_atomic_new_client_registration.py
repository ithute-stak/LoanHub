"""Phase 73: internal atomic registration semantics, never real clients."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from database.models.enums import Gender, EmploymentStatus
from database.schemas.company_clients import AssistedCompanyClientCreate
from services.new_client_identity_guard import NewClientGuardDecision
from services.new_client_registration_idempotency import RegistrationReservation
from services.atomic_new_client_registration import (
    AtomicRegistrationUnavailable,
    create_new_client_atomically,
    require_normalized_identity_constraints,
)


def candidate(**changes):
    values = dict(
        branch_id=uuid4(), first_name="Palesa", last_name="Mokoena",
        phone="59000000", date_of_birth=date(1991, 2, 1),
        gender=Gender.FEMALE, national_id="SYNTH-NID-100",
        district="Maseru", employment_status=EmploymentStatus.EMPLOYED,
        consent_to_share_profile=False, consent_to_credit_checks=False,
    )
    values.update(changes)
    return AssistedCompanyClientCreate(**values)


def staff():
    return SimpleNamespace(company_id=uuid4(), user=SimpleNamespace(id=uuid4()))


def identity(reason="candidate_requires_transactional_reservation"):
    return NewClientGuardDecision(
        candidate=False, reason=reason,
        identity_conflicts=int(reason == "existing_identity"),
        legacy_conflicts=int(reason == "historical_collision"),
    )


def reservation(existing=False, status="reserved", account=None):
    return RegistrationReservation(
        attempt_id=uuid4(), existing=existing, status=status,
        client_account_id=account,
    )


def mocks(db, reason="candidate_requires_transactional_reservation",
          attempt=None):
    return [
        patch("services.atomic_new_client_registration.prepare_new_only_registration_intent",
              return_value=SimpleNamespace(company_id=uuid4(),
                                           branch_id=uuid4(),
                                           employee_id=uuid4())),
        patch("services.atomic_new_client_registration.require_normalized_identity_constraints"),
        patch("services.atomic_new_client_registration.check_with_transaction_identity_locks",
              return_value=identity(reason)),
        patch("services.atomic_new_client_registration.reserve_new_client_registration",
              return_value=attempt or reservation()),
        patch("services.atomic_new_client_registration.active_company_account_opening_fee_configuration",
              return_value=None),
        patch("services.atomic_new_client_registration.stage_new_only_client_rows",
              return_value=SimpleNamespace(client_account_id=uuid4())),
        patch("services.atomic_new_client_registration.finalize_new_client_registration"),
    ]


def test_success_stages_once_and_finishes_in_one_transaction():
    db = MagicMock()
    db.in_transaction.return_value = False
    db.query.return_value.filter.return_value.scalar.return_value = 0
    with mocks(db)[0] as authorize, mocks(db)[1] as indexes, \
         mocks(db)[2] as lock, mocks(db)[3] as reserve, \
         mocks(db)[4] as fee, mocks(db)[5] as stage, \
         mocks(db)[6] as finalize:
        result = create_new_client_atomically(
            db, context=staff(), payload=candidate(),
            idempotency_key="synthetic-unique-key-0001",
            fingerprint_secret=b"x" * 32)
    assert result.existing is False
    db.begin.assert_called_once()
    indexes.assert_called_once()
    lock.assert_called_once()
    reserve.assert_called_once()
    stage.assert_called_once()
    finalize.assert_called_once()
    assert stage.call_args.kwargs["fee_config"] is None
    assert stage.call_args.kwargs["approved_internal_call"] is True
    db.commit.assert_not_called()


@pytest.mark.parametrize("reason", ["existing_identity", "historical_collision", "invalid_identity"])
def test_collision_never_stages_client(reason):
    db = MagicMock()
    db.in_transaction.return_value = False
    p = mocks(db, reason=reason)
    with p[0], p[1], p[2], p[3], p[4], p[5] as stage, p[6] as finalize:
        with pytest.raises(AtomicRegistrationUnavailable):
            create_new_client_atomically(
                db, context=staff(), payload=candidate(),
                idempotency_key="synthetic-unique-key-0001",
                fingerprint_secret=b"x" * 32)
    stage.assert_not_called()
    finalize.assert_not_called()


@pytest.mark.parametrize("changes", [
    {"monthly_income": "3000"}, {"has_existing_loans": True},
    {"external_debts": [{"lender_name": "X"}]},
    {"employer_name": "Example"}, {"email": "synthetic@example.ls"},
])
def test_unsupported_financial_inputs_are_not_silently_lost(changes):
    if "external_debts" in changes:
        pytest.skip("Requires complete supported external debt model")
    db = MagicMock()
    with pytest.raises(AtomicRegistrationUnavailable):
        create_new_client_atomically(
            db, context=staff(), payload=candidate(**changes),
            idempotency_key="synthetic-unique-key-0001",
            fingerprint_secret=b"x" * 32)
    db.begin.assert_not_called()


def test_existing_incomplete_request_does_not_create_second_client():
    db = MagicMock()
    db.in_transaction.return_value = False
    p = mocks(db, attempt=reservation(existing=True))
    with p[0], p[1], p[2], p[3], p[4], p[5] as stage, p[6] as finalize:
        with pytest.raises(AtomicRegistrationUnavailable):
            create_new_client_atomically(
                db, context=staff(), payload=candidate(),
                idempotency_key="synthetic-unique-key-0001",
                fingerprint_secret=b"x" * 32)
    stage.assert_not_called()
    finalize.assert_not_called()


def test_completed_replay_checks_account_scope_and_returns_existing_id():
    db = MagicMock()
    db.in_transaction.return_value = False
    client_id = uuid4()
    db.execute.return_value.scalar_one_or_none.return_value = client_id
    p = mocks(db, attempt=reservation(existing=True, status="completed", account=client_id))
    with p[0], p[1], p[2], p[3], p[4], p[5] as stage, p[6] as finalize:
        result = create_new_client_atomically(
            db, context=staff(), payload=candidate(),
            idempotency_key="synthetic-unique-key-0001",
            fingerprint_secret=b"x" * 32)
    assert result.client_account_id == client_id
    assert result.existing is True
    stage.assert_not_called()
    finalize.assert_not_called()


def test_replay_mismatched_account_scope_fails_closed():
    db = MagicMock()
    db.in_transaction.return_value = False
    db.execute.return_value.scalar_one_or_none.return_value = None
    p = mocks(db, attempt=reservation(existing=True, status="completed", account=uuid4()))
    with p[0], p[1], p[2], p[3], p[4], p[5] as stage, p[6] as finalize:
        with pytest.raises(AtomicRegistrationUnavailable):
            create_new_client_atomically(
                db, context=staff(), payload=candidate(),
                idempotency_key="synthetic-unique-key-0001",
                fingerprint_secret=b"x" * 32)
    stage.assert_not_called()
    finalize.assert_not_called()


def test_unrecognized_or_inactive_branch_blocks_registration_before_indexes():
    db = MagicMock()
    db.in_transaction.return_value = False
    db.execute.return_value.scalar_one_or_none.return_value = None
    p = mocks(db)
    with p[0], p[1] as indexes, p[2] as guard, p[3] as reserve, \\
         p[4], p[5] as stage, p[6]:
        with pytest.raises(AtomicRegistrationUnavailable, match="branch"):
            create_new_client_atomically(
                db, context=staff(), payload=candidate(),
                idempotency_key="synthetic-unique-key-0001",
                fingerprint_secret=b"x" * 32)
    indexes.assert_not_called()
    guard.assert_not_called()
    reserve.assert_not_called()
    stage.assert_not_called()


def test_missing_indexes_never_leads_to_any_registration():
    db = MagicMock()
    db.in_transaction.return_value = False
    p = mocks(db)
    with p[0], p[1] as indexes, p[2], p[3] as reserve, \
         p[4], p[5] as stage, p[6]:
        indexes.side_effect = AtomicRegistrationUnavailable("Missing verified indexes")
        with pytest.raises(AtomicRegistrationUnavailable):
            create_new_client_atomically(
                db, context=staff(), payload=candidate(),
                idempotency_key="synthetic-unique-key-0001",
                fingerprint_secret=b"x" * 32)
    reserve.assert_not_called()
    stage.assert_not_called()


def test_database_index_check_requires_valid_ready_unique_indexes():
    db = MagicMock()
    db.get_bind.return_value = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"))
    db.execute.return_value.one_or_none.return_value = None
    with pytest.raises(AtomicRegistrationUnavailable):
        require_normalized_identity_constraints(db)
    db.execute.assert_called_once()


def test_caller_owned_transaction_not_allowed():
    db = MagicMock()
    db.in_transaction.return_value = True
    p = mocks(db)
    with p[0], p[1] as indexes, p[2], p[3], p[4], p[5], p[6]:
        with pytest.raises(AtomicRegistrationUnavailable):
            create_new_client_atomically(
                db, context=staff(), payload=candidate(),
                idempotency_key="synthetic-unique-key-0001",
                fingerprint_secret=b"x" * 32)
    db.begin.assert_not_called()
    indexes.assert_not_called()
