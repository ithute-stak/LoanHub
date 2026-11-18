"""Phase 71 checks: no database mutation is permitted by coordinator."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from database.models.enums import Gender, EmploymentStatus
from services.new_client_identity_guard import NewClientGuardDecision
from services.new_client_transaction_coordinator import (
    ClientRegistrationNotActivated,
    plan_new_only_client_transaction,
    review_transaction_gate,
)
from services.new_only_client_registration import NewOnlyRegistrationIntent
from services.new_only_client_staging import MinimalNewClient


def intent():
    return NewOnlyRegistrationIntent(
        company_id=uuid4(), branch_id=uuid4(), employee_id=uuid4(),
        idempotency_key="synthetic-registration-0001",
        registration_fingerprint="a" * 64,
    )


def client():
    return MinimalNewClient(
        first_name="Palesa", last_name="Mokoena", phone="59000000",
        date_of_birth=date(1990, 1, 1), gender=Gender.FEMALE,
        national_id="SYNTHETIC-NID", passport_number=None,
        district="Maseru", employment_status=EmploymentStatus.EMPLOYED,
        consent_to_share_profile=False, consent_to_credit_checks=False,
    )


def database():
    db = MagicMock()
    db.get_bind.return_value = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"))
    db.in_transaction.return_value = True
    return db


def test_plan_is_safely_unexecutable_and_contains_no_pii():
    plan = plan_new_only_client_transaction(intent=intent(), payload=client())
    assert plan.can_execute is False
    assert plan.requires_database_constraints
    assert plan.requires_staging_certification
    assert "SYNTHETIC-NID" not in repr(plan)
    assert "59000000" not in repr(plan)


@pytest.mark.parametrize("reason", [
    "candidate_requires_transactional_reservation",
    "existing_identity",
    "historical_collision",
])
def test_all_screening_paths_block_writes(reason):
    db = database()
    evidence = NewClientGuardDecision(
        candidate=False, reason=reason,
        identity_conflicts=0, legacy_conflicts=0,
    )
    with patch(
        "services.new_client_transaction_coordinator.check_with_transaction_identity_locks",
        return_value=evidence,
    ) as check:
        with pytest.raises(ClientRegistrationNotActivated):
            review_transaction_gate(db, intent=intent(), payload=client())
    check.assert_called_once()
    db.add.assert_not_called()
    db.add_all.assert_not_called()
    db.commit.assert_not_called()
    db.flush.assert_not_called()


def test_wrong_database_is_denied_before_guard():
    db = database()
    db.get_bind.return_value.dialect.name = "sqlite"
    with patch(
        "services.new_client_transaction_coordinator.check_with_transaction_identity_locks"
    ) as check:
        with pytest.raises(ClientRegistrationNotActivated):
            review_transaction_gate(db, intent=intent(), payload=client())
    check.assert_not_called()
    db.execute.assert_not_called()


def test_missing_transaction_is_denied():
    db = database()
    db.in_transaction.return_value = False
    with pytest.raises(ClientRegistrationNotActivated):
        review_transaction_gate(db, intent=intent(), payload=client())
    db.add.assert_not_called()


def test_invalid_intent_is_rejected():
    db = database()
    with pytest.raises(ClientRegistrationNotActivated):
        review_transaction_gate(db, intent=None, payload=client())
    db.execute.assert_not_called()
