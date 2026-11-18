"""Phase 70: internal staging boundary and no-commit guarantees."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from database.models.enums import EmploymentStatus, Gender
from services.new_only_client_registration import NewOnlyRegistrationIntent
from services.new_only_client_staging import (
    MinimalNewClient, NewOnlyStagingDenied,
    stage_new_only_client_rows, validate_minimal_new_client,
)


def intent():
    return NewOnlyRegistrationIntent(
        company_id=uuid4(), branch_id=uuid4(), employee_id=uuid4(),
        idempotency_key="synthetic-idempotency-00001",
        registration_fingerprint="a" * 64,
    )


def client(**changes):
    data = dict(
        first_name="Palesa", last_name="Mokoena",
        phone="59000000", date_of_birth=date(1991, 2, 1),
        gender=Gender.FEMALE, national_id="SYNTH-NID-0001",
        passport_number=None, district="Maseru",
        employment_status=EmploymentStatus.EMPLOYED,
        consent_to_share_profile=False,
        consent_to_credit_checks=False,
    )
    data.update(changes)
    return MinimalNewClient(**data)


def postgres_db():
    db = MagicMock()
    db.get_bind.return_value = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"))
    db.in_transaction.return_value = True
    def simulate_flush():
        for record in db.add.call_args_list:
            model = record.args[0]
            if getattr(model, "id", None) is None:
                model.id = uuid4()
        for call in db.add_all.call_args_list:
            for model in call.args[0]:
                if getattr(model, "id", None) is None:
                    model.id = uuid4()
    db.flush.side_effect = simulate_flush
    return db


def test_staging_disabled_by_default_and_never_mutates():
    db = postgres_db()
    with pytest.raises(NewOnlyStagingDenied):
        stage_new_only_client_rows(
            db, intent=intent(), payload=client(),
            password_hash="h" * 60,
        )
    db.add.assert_not_called()
    db.add_all.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("change", [
    {"national_id": None, "passport_number": None},
    {"first_name": ""}, {"phone": "123"},
    {"date_of_birth": date.today()},
    {"consent_to_share_profile": "yes"},
])
def test_invalid_minimal_client_rejected(change):
    with pytest.raises(NewOnlyStagingDenied):
        validate_minimal_new_client(client(**change))


def test_staging_adds_new_objects_only_no_commit():
    db = postgres_db()
    i = intent()
    result = stage_new_only_client_rows(
        db, intent=i, payload=client(),
        password_hash="h" * 60,
        approved_internal_call=True,
    )
    assert result.company_id == i.company_id
    assert result.branch_id == i.branch_id
    assert db.add.call_count == 3
    assert db.add_all.call_count == 1
    assert db.flush.call_count == 4
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    models = [c.args[0].__class__.__name__
              for c in db.add.call_args_list]
    models.extend(m.__class__.__name__ for m in db.add_all.call_args.args[0])
    assert set(models) == {
        "User", "Person", "Borrower", "CompanyBorrowerAccount", "AuditLog",
    }


@pytest.mark.parametrize("dialect,in_tx", [
    ("sqlite", True), ("postgresql", False),
])
def test_requires_caller_owned_postgres_transaction(dialect, in_tx):
    db = postgres_db()
    db.get_bind.return_value.dialect.name = dialect
    db.in_transaction.return_value = in_tx
    with pytest.raises(NewOnlyStagingDenied):
        stage_new_only_client_rows(
            db, intent=intent(), payload=client(),
            password_hash="h" * 60, approved_internal_call=True,
        )
    db.add.assert_not_called()


def test_bad_password_hash_rejected_before_creating_any_rows():
    db = postgres_db()
    with pytest.raises(NewOnlyStagingDenied):
        stage_new_only_client_rows(
            db, intent=intent(), payload=client(),
            password_hash="plaintext", approved_internal_call=True,
        )
    db.add.assert_not_called()
