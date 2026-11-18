from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from services.identity_collision_audit import (
    IdentityCollisionAudit,
    _repeated_normalized_groups,
    inspect_identity_collisions,
)
from database.models.person import Person


def fake_db(dialect="postgresql"):
    db = MagicMock()
    db.get_bind.return_value = SimpleNamespace(
        dialect=SimpleNamespace(name=dialect))
    return db


def test_audit_returns_aggregate_counts_but_never_permission_to_register():
    db = fake_db()
    with patch("services.identity_collision_audit._repeated_normalized_groups",
               side_effect=[2, 1, 0, 3, 8]) as scan:
        result = inspect_identity_collisions(db)
    assert scan.call_count == 5
    assert result.person_national_id_groups == 2
    assert result.person_passport_groups == 1
    assert result.user_phone_groups == 0
    assert result.user_email_groups == 3
    assert result.repeated_legacy_capture_groups == 8
    assert result.safe_to_add_unique_indexes is False
    assert result.can_register_clients is False
    assert isinstance(result.checked_at, datetime)
    assert not hasattr(result, "identity_values")


@pytest.mark.parametrize("dialect", ["sqlite", "mysql"])
def test_non_postgres_is_rejected(dialect):
    db = fake_db(dialect)
    with pytest.raises(ValueError, match="PostgreSQL"):
        inspect_identity_collisions(db)
    db.query.assert_not_called()


def test_group_count_rejects_invalid_results():
    db = fake_db()
    db.query.return_value.select_from.return_value.scalar.return_value = -1
    with pytest.raises(ValueError):
        _repeated_normalized_groups(db, Person.national_id)


def test_group_count_uses_grouping_and_having_without_fetching_identities():
    db = fake_db()
    db.query.return_value.select_from.return_value.scalar.return_value = 4
    assert _repeated_normalized_groups(db, Person.national_id) == 4
    db.query.return_value.filter.return_value.group_by.return_value.having.assert_called_once()
    db.query.return_value.select_from.return_value.scalar.assert_called_once()
    db.query.return_value.all.assert_not_called()
