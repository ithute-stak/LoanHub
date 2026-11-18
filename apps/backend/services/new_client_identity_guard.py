"""Fail-closed, non-mutating checks before any *new-identity-only* registration.

This module does NOT approve writes or change legacy-assisted registration.
Existing Person and legacy captures are treated as conflicts, never linked
automatically. Database constraints and isolation still need separate
certification before this policy can be used in production.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database.models.person import Person
from database.models.user import User
from database.models.legacy_loan_capture import LegacyLoanCapture


@dataclass(frozen=True)
class NewClientGuardDecision:
    candidate: bool
    reason: str
    identity_conflicts: int
    legacy_conflicts: int


def _normalize(value: str | None) -> str:
    return value.strip().casefold() if isinstance(value, str) else ""


def inspect_new_client_candidate(
    db: Session,
    *,
    company_id: UUID,
    national_id: str | None,
    passport_number: str | None,
    phone: str,
    email: str | None = None,
) -> NewClientGuardDecision:
    """Return only a coarse decision, never matched borrowers or personal data.

    An empty result is *not* a transactional reservation and is not permission
    to call the legacy assisted-create route: another writer may race with it.
    """
    if not isinstance(company_id, UUID):
        raise ValueError("Verified company UUID required")
    nid, passport, phone_value, email_value = (
        _normalize(national_id), _normalize(passport_number),
        _normalize(phone), _normalize(email),
    )
    if not (nid or passport) or not 8 <= len(phone_value) <= 30:
        return NewClientGuardDecision(False, "invalid_identity", 0, 0)
    if any(len(v) > 100 for v in (nid, passport)):
        return NewClientGuardDecision(False, "invalid_identity", 0, 0)

    identity_filters = []
    if nid:
        identity_filters.append(
            func.lower(func.trim(Person.national_id)) == nid)
    if passport:
        identity_filters.append(
            func.lower(func.trim(Person.passport_number)) == passport)
    person_count = db.query(func.count(Person.user_id)).filter(
        or_(*identity_filters)).scalar() or 0

    user_filters = [func.lower(func.trim(User.phone)) == phone_value]
    if email_value:
        user_filters.append(func.lower(func.trim(User.email)) == email_value)
    user_count = db.query(func.count(User.id)).filter(
        or_(*user_filters)).scalar() or 0

    legacy_count = 0
    if nid:
        legacy_count = db.query(func.count(LegacyLoanCapture.id)).filter(
            LegacyLoanCapture.company_id == company_id,
            func.lower(func.trim(LegacyLoanCapture.national_id)) == nid,
        ).scalar() or 0

    for value in (person_count, user_count, legacy_count):
        if type(value) is not int or value < 0:
            raise ValueError("Untrustworthy candidate evidence")
    reason = ("existing_identity" if person_count or user_count else
              "historical_collision" if legacy_count else
              "candidate_requires_transactional_reservation")
    return NewClientGuardDecision(
        candidate=False,  # No writes until safe transaction is certified.
        reason=reason,
        identity_conflicts=person_count + user_count,
        legacy_conflicts=legacy_count,
    )
