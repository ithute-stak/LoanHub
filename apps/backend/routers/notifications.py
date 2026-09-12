from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from core.access_control import get_current_active_user
from database.models.enums import NotificationType
from database.models.notification import Notification
from database.models.user import User
from database.schemas.notification import (
    NotificationListRead,
    NotificationRead,
    NotificationUnreadCountRead,
)
from database.session import get_db


router = APIRouter(prefix="/notifications", tags=["Notifications"])

# Notifications are for events that need a person's attention. Routine CRUD and
# presence/activity events belong in the audit/activity log and are intentionally
# hidden from the normal notification inbox. Keeping the filter centralized here
# also protects the UI from older producers that still persist low-value rows.
ATTENTION_NOTIFICATION_TYPES = (
    NotificationType.LOAN_REQUEST,
    NotificationType.ACCESS_REQUEST,
    NotificationType.OFFER,
    NotificationType.PAYMENT,
    NotificationType.SUBSCRIPTION,
)
ATTENTION_PRIORITIES = ("critical", "high", "urgent")


def attention_notification_filter():
    return or_(
        func.lower(Notification.priority).in_(ATTENTION_PRIORITIES),
        Notification.notification_type.in_(ATTENTION_NOTIFICATION_TYPES),
    )


def notification_or_404(db: Session, notification_id: UUID, user_id: UUID) -> Notification:
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.get("", response_model=NotificationListRead)
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = False,
    include_archived: bool = False,
    event_type: str | None = None,
    attention_only: bool = True,
    include_routine: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)

    if not include_archived:
        query = query.filter(Notification.is_archived.is_(False))
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    if event_type:
        query = query.filter(Notification.event_type == event_type)

    # Normal product surfaces always show attention-worthy events. The explicit
    # include_routine escape hatch exists for administrators/support tooling and
    # backwards compatibility; it must be requested deliberately.
    if (attention_only or not include_routine) and not event_type:
        query = query.filter(attention_notification_filter())

    total = query.count()
    unread_query = db.query(func.count(Notification.id)).filter(
        Notification.user_id == current_user.id,
        Notification.is_read.is_(False),
        Notification.is_archived.is_(False),
    )
    if (attention_only or not include_routine) and not event_type:
        unread_query = unread_query.filter(attention_notification_filter())
    unread_count = unread_query.scalar() or 0

    items = (
        query.order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return NotificationListRead(
        items=[NotificationRead.model_validate(item) for item in items],
        total=total,
        unread_count=unread_count,
        page=page,
        page_size=page_size,
    )


@router.get("/unread-count", response_model=NotificationUnreadCountRead)
def unread_count(
    include_routine: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(func.count(Notification.id)).filter(
        Notification.user_id == current_user.id,
        Notification.is_read.is_(False),
        Notification.is_archived.is_(False),
    )
    if not include_routine:
        query = query.filter(attention_notification_filter())
    return NotificationUnreadCountRead(unread_count=query.scalar() or 0)


@router.patch("/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    notification = notification_or_404(db, notification_id, current_user.id)
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db.commit()
        db.refresh(notification)
    return notification


@router.patch("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(
    include_routine: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read.is_(False),
        Notification.is_archived.is_(False),
    )
    if not include_routine:
        query = query.filter(attention_notification_filter())
    query.update(
        {
            Notification.is_read: True,
            Notification.read_at: datetime.utcnow(),
        },
        synchronize_session=False,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{notification_id}/archive", response_model=NotificationRead)
def archive_notification(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    notification = notification_or_404(db, notification_id, current_user.id)
    notification.is_archived = True
    notification.archived_at = datetime.utcnow()
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.utcnow()
    db.commit()
    db.refresh(notification)
    return notification


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    notification = notification_or_404(db, notification_id, current_user.id)
    db.delete(notification)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
