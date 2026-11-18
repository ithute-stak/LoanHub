"""Read-only aggregate audit of normalized borrower identity collisions.

Phase 65 deliberately returns counts only, never identity values. It does not
alter records, create indexes, deduplicate people or activate registration.
Run only through an approved operator-controlled, read-only database session.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models.person import Person
from database.models.user import User
from database.models.legacy_loan_capture import LegacyLoanCapture


@dataclass(frozen=True)
class IdentityCollisionAudit:
    checked_at: datetime
    person_national_id_groups: int
    person_passport_groups: int
    user_phone_groups: int
    user_email_groups: int
    repeated_legacy_capture_groups: int
    safe_to_add_unique_indexes: bool = False
    can_register_clients: bool = False


def _repeated_normalized_groups(db: Session, column) -> int:
    """Count ambiguous normalized keys; never materialize the raw keys."""
    normalized = func.lower(func.trim(column))
    groups = (
        db.query(normalized.label("normalized_identity"))
        .filter(column.isnot(None), func.length(func.trim(column)) > 0)
        .group_by(normalized)
        .having(func.count() > 1)
        .subquery()
    )
    count = db.query(func.count()).select_from(groups).scalar()
    if type(count) is not int or count < 0:
        raise ValueError("Identity collision audit returned invalid counts")
    return count


def inspect_identity_collisions(db: Session) -> IdentityCollisionAudit:
    """Global scan: do not add tenant filters to the Person/User checks.

    Person and User identities are globally shared, unlike company-owned
    accounts. Repeated legacy captures can represent legitimate installments
    or different loans; they are review signals, not automatic duplicates.
    """
    if db.get_bind() is None or db.get_bind().dialect.name != "postgresql":
        raise ValueError("Identity audit requires PostgreSQL")
    return IdentityCollisionAudit(
        checked_at=datetime.now(timezone.utc),
        person_national_id_groups=_repeated_normalized_groups(db, Person.national_id),
        person_passport_groups=_repeated_normalized_groups(db, Person.passport_number),
        user_phone_groups=_repeated_normalized_groups(db, User.phone),
        user_email_groups=_repeated_normalized_groups(db, User.email),
        repeated_legacy_capture_groups=_repeated_normalized_groups(
            db, LegacyLoanCapture.national_id),
    )
