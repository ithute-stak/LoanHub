from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from services.identity_index_readiness import (
    PROPOSED_INDEX_DEFINITIONS,
    REQUIRED_INDEX_SPECS,
    inspect_identity_index_readiness,
)


def db_with_indexes(results, dialect="postgresql"):
    db = MagicMock()
    db.get_bind.return_value = SimpleNamespace(
        dialect=SimpleNamespace(name=dialect))
    db.execute.return_value.first.side_effect = results
    return db


def collisions(*counts):
    return SimpleNamespace(
        person_national_id_groups=counts[0],
        person_passport_groups=counts[1],
        user_phone_groups=counts[2],
        user_email_groups=counts[3],
        repeated_legacy_capture_groups=0,
    )


def test_no_collisions_still_does_not_approve_migration():
    db = db_with_indexes([None] * 4)
    with patch("services.identity_index_readiness.inspect_identity_collisions",
               return_value=collisions(0, 0, 0, 0)):
        report = inspect_identity_index_readiness(db)
    assert report.migration_review_candidate is True
    assert report.safe_to_apply_migration is False
    assert report.registration_enabled is False
    assert len(report.missing_or_invalid_indexes) == 4
    assert db.execute.call_count == 4
    assert all("index_name" in call.args[1]
               for call in db.execute.call_args_list)


def test_detects_existing_valid_indexes_without_enabling_registration():
    index_data = [
        (True, True, "CREATE UNIQUE INDEX uq_people_national_id_normalized "
                     "ON people USING btree (lower(btrim(national_id)))"),
        (True, True, "CREATE UNIQUE INDEX uq_people_passport_normalized "
                     "ON people USING btree (lower(btrim(passport_number)))"),
        (True, True, "CREATE UNIQUE INDEX uq_users_phone_normalized "
                     "ON users USING btree (lower(btrim(phone)))"),
        (True, True, "CREATE UNIQUE INDEX uq_users_email_normalized "
                     "ON users USING btree (lower(btrim(email)))"),
    ]
    db = db_with_indexes(index_data)
    with patch("services.identity_index_readiness.inspect_identity_collisions",
               return_value=collisions(0, 0, 0, 0)):
        report = inspect_identity_index_readiness(db)
    assert len(report.present_valid_indexes) == 4
    assert not report.registration_enabled
    assert not report.safe_to_apply_migration


def test_invalid_and_nonunique_indexes_rejected():
    db = db_with_indexes([
        (False, True, "lower(btrim(national_id))"),
        (True, False, "lower(btrim(passport_number))"),
        (True, True, "raw unnormalized phone"),
        None,
    ])
    with patch("services.identity_index_readiness.inspect_identity_collisions",
               return_value=collisions(0, 1, 0, 0)):
        report = inspect_identity_index_readiness(db)
    assert not report.migration_review_candidate
    assert len(report.missing_or_invalid_indexes) == 4


@pytest.mark.parametrize("dialect", ["sqlite", "mysql"])
def test_non_postgres_rejected(dialect):
    db = db_with_indexes([], dialect=dialect)
    with pytest.raises(ValueError, match="PostgreSQL"):
        inspect_identity_index_readiness(db)
    db.execute.assert_not_called()


def test_proposed_ddl_is_never_run_by_readiness_check():
    assert len(PROPOSED_INDEX_DEFINITIONS) == len(REQUIRED_INDEX_SPECS)
    assert all("CREATE UNIQUE INDEX CONCURRENTLY" in ddl
               for ddl in PROPOSED_INDEX_DEFINITIONS)
    db = db_with_indexes([None] * 4)
    with patch("services.identity_index_readiness.inspect_identity_collisions",
               return_value=collisions(0, 0, 0, 0)):
        inspect_identity_index_readiness(db)
    assert all("CREATE" not in str(call.args[0]).upper()
               for call in db.execute.call_args_list)
