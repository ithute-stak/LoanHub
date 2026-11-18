"""Phase 77: negative security contracts for read-only rollout preflight."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from services.identity_index_rollout_preflight import (
    IndexRolloutPreflightError, inspect_index_rollout_preflight,
)


def db_mock(*, dialect="postgresql", transaction=True, read_only="on"):
    db = MagicMock()
    db.get_bind.return_value = SimpleNamespace(
        dialect=SimpleNamespace(name=dialect))
    db.in_transaction.return_value = transaction
    db.execute.return_value.scalar_one.side_effect = [
        read_only, 0, 0, 0, 0,
    ]
    return db


@pytest.mark.parametrize("dialect,transaction", [
    ("sqlite", True), ("mysql", True), ("postgresql", False),
])
def test_requires_postgres_and_existing_read_only_transaction(dialect, transaction):
    db = db_mock(dialect=dialect, transaction=transaction)
    with pytest.raises(IndexRolloutPreflightError):
        inspect_index_rollout_preflight(db)
    db.execute.assert_not_called()


def test_writable_transaction_rejected_before_any_identity_table_scan():
    db = db_mock(read_only="off")
    with patch(
        "services.identity_index_rollout_preflight.inspect_identity_index_readiness"
    ) as readiness:
        with pytest.raises(IndexRolloutPreflightError, match="Read-only"):
            inspect_index_rollout_preflight(db)
    readiness.assert_not_called()
    assert db.execute.call_count == 1


@pytest.mark.parametrize("collisions,blanks,review", [
    ((0, 0, 0, 0), (0, 0, 0, 0), True),
    ((1, 0, 0, 0), (0, 0, 0, 0), False),
    ((0, 0, 0, 0), (0, 1, 0, 0), True),
])
def test_preflight_never_authorizes_ddl_or_live_registration(
    collisions, blanks, review,
):
    db = db_mock()
    db.execute.return_value.scalar_one.side_effect = ["on", *blanks]
    scan = SimpleNamespace(
        duplicate_group_counts=collisions,
        missing_or_invalid_indexes=("uq_users_phone_normalized",),
        migration_review_candidate=review,
    )
    with patch(
        "services.identity_index_rollout_preflight.inspect_identity_index_readiness",
        return_value=scan,
    ):
        result = inspect_index_rollout_preflight(db)
    assert result.collision_groups == collisions
    assert result.empty_identity_counts == blanks
    assert result.requires_manual_legacy_reconciliation == bool(
        any(collisions) or any(blanks))
    assert result.operator_review_candidate == (review and not any(blanks))
    assert result.safe_to_execute is False
    assert result.production_approved is False
    assert result.registration_enabled is False
    assert len(result.proposed_statements) == 4
    assert all(statement.startswith("CREATE UNIQUE INDEX CONCURRENTLY")
               for statement in result.proposed_statements)
    assert all("INSERT" not in str(call.args[0]).upper()
               and "UPDATE" not in str(call.args[0]).upper()
               and "CREATE" not in str(call.args[0]).upper()
               for call in db.execute.call_args_list)


def test_non_numeric_scan_fails_closed():
    db = db_mock()
    db.execute.return_value.scalar_one.side_effect = ["on", 0, None]
    scan = SimpleNamespace(
        duplicate_group_counts=(0, 0, 0, 0),
        missing_or_invalid_indexes=(),
        migration_review_candidate=True,
    )
    with patch(
        "services.identity_index_rollout_preflight.inspect_identity_index_readiness",
        return_value=scan,
    ):
        with pytest.raises(IndexRolloutPreflightError):
            inspect_index_rollout_preflight(db)
