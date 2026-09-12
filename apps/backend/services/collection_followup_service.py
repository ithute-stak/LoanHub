from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.access_control import COLLECTIONS_ROLES
from database.config.config import settings
from database.models.company_staff import CompanyStaff
from database.models.enums import NotificationType
from database.models.lending_operations import CollectionCase
from database.models.notification import Notification
from database.models.user import User

CLAIM_TTL_MINUTES = 20


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _claim_active(case: CollectionCase, now: datetime) -> bool:
    expires = case.action_claim_expires_at
    if not case.action_claimed_by_user_id or not expires:
        return False
    return expires > (now.replace(tzinfo=None) if expires.tzinfo is None else now)


def claim_collection_case(db: Session, case: CollectionCase, user_id: UUID, *, ttl_minutes: int = CLAIM_TTL_MINUTES) -> CollectionCase:
    now = _utcnow()
    row = db.query(CollectionCase).filter(CollectionCase.id == case.id).with_for_update().one()
    if _claim_active(row, now) and row.action_claimed_by_user_id != user_id:
        owner = db.get(User, row.action_claimed_by_user_id)
        person = getattr(owner, "person", None) if owner else None
        display = " ".join(v for v in [getattr(person, "first_name", None), getattr(person, "last_name", None)] if v) if person else ""
        raise HTTPException(status_code=409, detail=f"This recovery case is currently being handled by {display or 'another staff member'}.")
    row.action_claimed_by_user_id = user_id
    row.action_claimed_at = now
    row.action_claim_expires_at = now + timedelta(minutes=max(5, min(ttl_minutes, 120)))
    db.flush()
    return row


def assert_or_claim_collection_case(db: Session, case: CollectionCase, user_id: UUID) -> CollectionCase:
    return claim_collection_case(db, case, user_id)


def release_collection_case_claim(db: Session, case: CollectionCase, user_id: UUID, *, force: bool = False) -> None:
    row = db.query(CollectionCase).filter(CollectionCase.id == case.id).with_for_update().one()
    if not force and row.action_claimed_by_user_id not in {None, user_id}:
        raise HTTPException(status_code=409, detail="Only the staff member handling this case can release it")
    row.action_claimed_by_user_id = row.action_claimed_at = row.action_claim_expires_at = None
    db.flush()


def _recipients(db: Session, case: CollectionCase) -> list[UUID]:
    if case.assigned_to_user_id and db.query(CompanyStaff.id).filter(
        CompanyStaff.company_id == case.company_id,
        CompanyStaff.user_id == case.assigned_to_user_id,
        CompanyStaff.is_active.is_(True),
    ).first():
        return [case.assigned_to_user_id]
    query = db.query(CompanyStaff).filter(
        CompanyStaff.company_id == case.company_id,
        CompanyStaff.is_active.is_(True),
        CompanyStaff.role.in_(list(COLLECTIONS_ROLES)),
    )
    if case.branch_id:
        query = query.filter((CompanyStaff.branch_id == case.branch_id) | CompanyStaff.branch_id.is_(None))
    return list(dict.fromkeys(row.user_id for row in query.all()))


def _notify_once(db: Session, case: CollectionCase, user_id: UUID, kind: str, action_day, next_dt) -> int:
    key = f"collection-reminder:{case.id}:{user_id}:{kind}"
    if db.query(Notification.id).filter(Notification.deduplication_key == key).first():
        return 0
    due_word = "today" if action_day <= datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date() else "tomorrow"
    db.add(Notification(
        user_id=user_id,
        company_id=case.company_id,
        branch_id=case.branch_id,
        title=f"Collection follow-up due {due_word}",
        message=f"Recovery case {case.case_reference} has a next action {due_word} ({action_day.isoformat()}). Claim the case before contacting the borrower.",
        notification_type=NotificationType.SYSTEM,
        event_type="collection.follow_up.reminder",
        action="view",
        entity_type="collection_case",
        entity_id=str(case.id),
        action_url=f"/company/collections?case={case.id}",
        icon="calendar-clock",
        priority="urgent" if due_word == "today" else "high",
        data={"case_reference": case.case_reference, "next_action_at": next_dt.isoformat(), "kind": kind},
        deduplication_key=key,
    ))
    return 1


def process_collection_reminders(db: Session, *, now: datetime | None = None, company_id: UUID | None = None) -> int:
    zone = ZoneInfo(settings.APP_TIMEZONE)
    local_now = now.astimezone(zone) if now and now.tzinfo else (now.replace(tzinfo=zone) if now else datetime.now(zone))
    if local_now.hour < 7:
        return 0
    today = local_now.date()
    query = db.query(CollectionCase).filter(
        CollectionCase.next_action_at.is_not(None),
        CollectionCase.status.notin_(["closed", "recovered", "written_off"]),
    )
    if company_id:
        query = query.filter(CollectionCase.company_id == company_id)
    created = 0
    for case in query.all():
        next_dt = case.next_action_at
        action_local = next_dt.astimezone(zone) if next_dt.tzinfo else next_dt.replace(tzinfo=zone)
        action_day = action_local.date()
        if action_day == today + timedelta(days=1):
            kind = "tomorrow"
        elif action_day == today:
            kind = "today"
        elif action_day < today:
            kind = f"overdue-{today.isoformat()}"
        else:
            continue
        for user_id in _recipients(db, case):
            created += _notify_once(db, case, user_id, kind, action_day, next_dt)
    return created
