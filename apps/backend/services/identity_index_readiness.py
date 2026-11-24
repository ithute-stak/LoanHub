"""Phase 66: read-only PostgreSQL normalized-identity index readiness audit.

This is NOT a migration executor. It never creates indexes, locks tables or
modifies client/loan data. A passing scan is insufficient to approve a
concurrent migration or enable any registration endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.identity_collision_audit import (
    IdentityCollisionAudit,
    inspect_identity_collisions,
)

# Explicit, non-PII index names. Do not dynamically interpolate user input
# into DDL or SQL identifiers.
REQUIRED_INDEX_SPECS = (
    ("people", "national_id", "uq_people_national_id_normalized"),
    ("people", "passport_number", "uq_people_passport_normalized"),
    ("users", "phone", "uq_users_phone_normalized"),
    ("users", "email", "uq_users_email_normalized"),
)

# For design review ONLY: deliberately no actual DDL is executed here.
PROPOSED_INDEX_DEFINITIONS = (
    "CREATE UNIQUE INDEX CONCURRENTLY uq_people_national_id_normalized "
    "ON people (lower(btrim(national_id))) "
    "WHERE national_id IS NOT NULL AND btrim(national_id) <> '';",
    "CREATE UNIQUE INDEX CONCURRENTLY uq_people_passport_normalized "
    "ON people (lower(btrim(passport_number))) "
    "WHERE passport_number IS NOT NULL AND btrim(passport_number) <> '';",
    "CREATE UNIQUE INDEX CONCURRENTLY uq_users_phone_normalized "
    "ON users (lower(btrim(phone))) "
    "WHERE phone IS NOT NULL AND btrim(phone) <> '';",
    "CREATE UNIQUE INDEX CONCURRENTLY uq_users_email_normalized "
    "ON users (lower(btrim(email))) "
    "WHERE email IS NOT NULL AND btrim(email) <> '';",
)


@dataclass(frozen=True)
class IdentityIndexReadiness:
    checked_at: datetime
    duplicate_group_counts: tuple[int, int, int, int]
    proposed_index_names: tuple[str, ...]
    present_valid_indexes: tuple[str, ...]
    missing_or_invalid_indexes: tuple[str, ...]
    migration_review_candidate: bool
    safe_to_apply_migration: bool = False
    registration_enabled: bool = False


def inspect_identity_index_readiness(db: Session) -> IdentityIndexReadiness:
    """Audit a reporting/staging PostgreSQL snapshot with a read-only role."""
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        raise ValueError("PostgreSQL required for identity-index readiness")
    collisions: IdentityCollisionAudit = inspect_identity_collisions(db)
    counts = (
        collisions.person_national_id_groups,
        collisions.person_passport_groups,
        collisions.user_phone_groups,
        collisions.user_email_groups,
    )
    present = []
    missing = []
    for table, column, index_name in REQUIRED_INDEX_SPECS:
        # Verify both validity and uniqueness: an index with the expected name
        # alone does not guarantee its expression/predicate is correct. Exact
        # index definitions must still be verified by an independent DBA.
        result = db.execute(text("""
            SELECT i.indisvalid, i.indisunique, i.indisready,
                   pg_get_expr(i.indexprs, i.indrelid),
                   pg_get_expr(i.indpred, i.indrelid)
            FROM pg_class AS c
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            JOIN pg_index AS i ON i.indexrelid = c.oid
            JOIN pg_class AS t ON t.oid = i.indrelid
            WHERE n.nspname = current_schema()
              AND t.relname = :table_name
              AND c.relname = :index_name
        """), {"table_name": table, "index_name": index_name}).first()
        expr = str(result[3]).lower() if result is not None else ""
        normalized_expr = re.sub(r"\\s+", "", expr)
        compact_expr = normalized_expr.replace("(", "").replace(")", "")
        predicate = str(result[4]) if result is not None else ""
        # Mirror the real atomic writer's index gate: uniqueness, validity,
        # readiness, actual normalized expression, and non-null predicate.
        if (
            result is not None
            and all(value is True for value in result[:3])
            and normalized_expr.startswith("lower(btrim(")
            and column in compact_expr
            and "lower" in compact_expr and "btrim" in compact_expr
            and column in predicate
            and "IS NOT NULL" in predicate.upper()
        ):
            present.append(index_name)
        else:
            missing.append(index_name)
    return IdentityIndexReadiness(
        checked_at=datetime.now(timezone.utc),
        duplicate_group_counts=counts,
        proposed_index_names=tuple(spec[2] for spec in REQUIRED_INDEX_SPECS),
        present_valid_indexes=tuple(present),
        missing_or_invalid_indexes=tuple(missing),
        migration_review_candidate=all(count == 0 for count in counts),
    )
