from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from services.new_client_identity_guard import inspect_new_client_candidate


def db_with_counts(person=0, user=0, legacy=0):
    db = MagicMock()
    db.query.return_value.filter.return_value.scalar.side_effect = [
        person, user, legacy,
    ]
    return db


def inspect(db, **changes):
    kwargs = dict(
        company_id=uuid4(), national_id="SYNTH-1234",
        passport_number=None, phone="59000000", email=None,
    )
    kwargs.update(changes)
    return inspect_new_client_candidate(db, **kwargs)


def test_no_matches_never_authorizes_a_write():
    result = inspect(db_with_counts())
    assert not result.candidate
    assert result.reason == "candidate_requires_transactional_reservation"
    assert result.identity_conflicts == 0


@pytest.mark.parametrize("counts,reason", [
    ((1, 0, 0), "existing_identity"),
    ((0, 1, 0), "existing_identity"),
    ((0, 0, 2), "historical_collision"),
    ((1, 0, 2), "existing_identity"),
])
def test_existing_identity_and_legacy_records_are_blocked(counts, reason):
    result = inspect(db_with_counts(*counts))
    assert result.reason == reason
    assert result.candidate is False


def test_missing_identity_is_rejected_before_query():
    db = MagicMock()
    result = inspect(db, national_id=None, passport_number=None)
    assert result.reason == "invalid_identity"
    db.query.assert_not_called()


def test_passport_only_is_checked_against_legacy_captures():
    result = inspect(
        db_with_counts(0, 0, 1),
        national_id=None, passport_number="SYNTHETIC",
    )
    assert not result.candidate
    assert result.reason == "historical_collision"
    assert result.legacy_conflicts == 1


def test_passport_only_without_legacy_match_remains_fail_closed():
    result = inspect(
        db_with_counts(0, 0, 0),
        national_id=None, passport_number="SYNTHETIC",
    )
    assert result.candidate is False
    assert result.reason == "candidate_requires_transactional_reservation"


def test_invalid_db_evidence_rejected():
    with pytest.raises(ValueError):
        inspect(db_with_counts(person=-1))


def test_no_personal_data_in_decision():
    result = inspect(db_with_counts())
    assert "SYNTH-1234" not in str(result)
    assert "59000000" not in str(result)
