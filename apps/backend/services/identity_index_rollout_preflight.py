"""Phase 77: read-only operational preflight for normalized identity indexes.

Intentionally has no DDL execution and never approves a production rollout.
The output is limited to aggregate collision counts and index metadata.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.identity_index_readiness import (
    REQUIRED_INDEX_SPECS,
    PROPOSED_INDEX_DEFINITIONS,
    inspect_identity_index_readiness,
)


@dataclass(frozen=True)
class IndexRolloutPreflight:
    checked_at: datetime
    database_kind: str
    collision_groups: tuple[int, int, int, int]
    empty_identity_counts: tuple[int, int, int, int]
    invalid_existing_index_names: tuple[str, ...]
    proposed_statements: tuple[str, ...]
    requires_manual_legacy_reconciliation: bool
    operator_review_candidate: bool
    safe_to_execute: bool = False
    production_approved: bool = False
    registration_enabled: bool = False


class IndexRolloutPreflightError(RuntimeError):
    pass


def inspect_index_rollout_preflight(db: Session) -> IndexRolloutPreflight:
    """Inspect non-sensitive aggregates through a transaction's read-only role.

    Never enumerate personal identifiers, return matched records, add an
    identity index, or change a user's accounts, loans or settlements.
    """
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        raise IndexRolloutPreflightError("PostgreSQL is required")
    if not db.in_transaction():
        raise IndexRolloutPreflightError("Read-only caller transaction required")
    access = db.execute(text(
        "SELECT current_setting('transaction_read_only')"
    )).scalar_one()
    if access != "on":
        raise IndexRolloutPreflightError("Read-only transaction required")

    readiness = inspect_identity_index_readiness(db)
    blank_counts: list[int] = []
    for table_name, column_name, _index_name in REQUIRED_INDEX_SPECS:
        # Names are fixed constants from audited source code, not input.
        count = db.execute(text(
            f"SELECT count(*) FROM {table_name} "
            f"WHERE {column_name} IS NOT NULL "
            f"AND btrim({column_name}) = ''"
        )).scalar_one()
        if type(count) is not int or count < 0:
            raise IndexRolloutPreflightError("Unreliable identity field audit")
        blank_counts.append(count)

    # A preview is not permission to execute DDL. Existing index metadata
    # may still need an independent DBA inspection for predicate/collation.
    return IndexRolloutPreflight(
        checked_at=datetime.now(timezone.utc),
        database_kind="postgresql",
        collision_groups=readiness.duplicate_group_counts,
        empty_identity_counts=tuple(blank_counts),
        invalid_existing_index_names=readiness.missing_or_invalid_indexes,
        proposed_statements=PROPOSED_INDEX_DEFINITIONS,
        requires_manual_legacy_reconciliation=bool(
            any(readiness.duplicate_group_counts)
            or any(blank_counts)
        ),
        operator_review_candidate=bool(
            readiness.migration_review_candidate
            and not any(blank_counts)
        ),
    )
