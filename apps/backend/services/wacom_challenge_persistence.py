"""Atomic one-time Wacom workstation challenge consumption.

The caller must have already verified the Ed25519 proof against the
enrollment's trusted public key and authenticated tenant/session context.
This is a persistence primitive, not an exposed endpoint.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, exists, select, update
from sqlalchemy.orm import Session

from database.models.wacom_workstation import (
    WacomWorkstationChallengeRecord,
    WacomWorkstationEnrollment,
)


def consume_verified_wacom_challenge(
    db: Session,
    *,
    challenge_id: UUID,
    company_id: UUID,
    enrollment_id: UUID,
    session_id: UUID,
    now: datetime,
) -> bool:
    """Atomically mark a matching, still-active proof challenge consumed.

    Must be invoked in a transaction that the authenticated caller commits.
    A revoked enrollment, expired challenge, wrong tenant or replay returns
    False. No acceptance occurs on database failure.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware time required")
    active_enrollment = exists(
        select(WacomWorkstationEnrollment.id).where(
            WacomWorkstationEnrollment.id == enrollment_id,
            WacomWorkstationEnrollment.company_id == company_id,
            WacomWorkstationEnrollment.status == "active",
            WacomWorkstationEnrollment.revoked_at.is_(None),
            WacomWorkstationEnrollment.approved_at.is_not(None),
        )
    )
    statement = (
        update(WacomWorkstationChallengeRecord)
        .where(
            WacomWorkstationChallengeRecord.id == challenge_id,
            WacomWorkstationChallengeRecord.company_id == company_id,
            WacomWorkstationChallengeRecord.enrollment_id == enrollment_id,
            WacomWorkstationChallengeRecord.session_id == session_id,
            WacomWorkstationChallengeRecord.consumed_at.is_(None),
            WacomWorkstationChallengeRecord.expires_at > now,
            active_enrollment,
        )
        .values(consumed_at=now)
        .returning(WacomWorkstationChallengeRecord.id)
    )
    return db.execute(statement).scalar_one_or_none() == challenge_id
