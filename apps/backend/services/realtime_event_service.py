from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from core.websocket_manager import manager
from database.models.borrower import Borrower
from database.models.company_staff import CompanyStaff
from database.models.enums import UserRole
from database.models.payment import PaymentTransaction
from database.models.user import User
from services.mobile_push_service import send_push_event

_RESERVED = {"type", "event_id", "domain", "occurred_at", "entity_id", "data", "notification"}


def build_realtime_event(
    event_type: str,
    *,
    domain: str,
    entity_id: UUID | str | None = None,
    data: dict[str, Any] | None = None,
    notification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the contract shared by WebSocket, BLoCs and background push."""

    payload_data = dict(data or {})
    event: dict[str, Any] = {
        "type": event_type,
        "event_id": str(uuid.uuid4()),
        "domain": domain,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "entity_id": str(entity_id) if entity_id is not None else None,
        "data": payload_data,
    }
    if notification:
        event["notification"] = notification
    # Existing web consumers read many fields at the top level. Mirror data
    # there while keeping the typed v1 envelope for the mobile BLoCs.
    for key, value in payload_data.items():
        if key not in _RESERVED:
            event[key] = value
    return event


async def emit_realtime_event(
    user_ids: Iterable[UUID | str],
    event: dict[str, Any],
    *,
    push: bool = False,
) -> None:
    recipients = list(dict.fromkeys(user_ids))
    for user_id in recipients:
        await manager.send_to_user(str(user_id), event)
    # Most pushes are handled by the manager bridge. Explicit push is useful
    # for events that are not otherwise sent one recipient at a time.
    if push and event.get("notification"):
        await send_push_event(recipients, event)


def payment_recipient_user_ids(
    db: Session,
    payment: PaymentTransaction,
) -> list[UUID]:
    """Resolve users who should see a provider-confirmed incoming payment.

    The recipient is inferred only from server-owned LoanHub records. A client
    cannot choose arbitrary users to receive a financial notification.
    """

    recipients: set[UUID] = set()

    if payment.payee_phone:
        payee = (
            db.query(User.id)
            .filter(
                User.phone == payment.payee_phone,
                User.is_active.is_(True),
            )
            .first()
        )
        if payee:
            recipients.add(payee[0])

    if payment.borrower_id:
        borrower_user = (
            db.query(Borrower.user_id)
            .filter(Borrower.id == payment.borrower_id)
            .first()
        )
        if borrower_user and borrower_user[0] and payment.direction.value == "outbound":
            recipients.add(borrower_user[0])

    if payment.company_id and payment.direction.value == "inbound":
        finance_roles = {
            UserRole.COMPANY_OWNER,
            UserRole.COMPANY_ADMIN,
            UserRole.FINANCE_OFFICER,
            UserRole.TREASURY_OFFICER,
            UserRole.BRANCH_MANAGER,
        }
        rows = (
            db.query(CompanyStaff.user_id)
            .filter(
                CompanyStaff.company_id == payment.company_id,
                CompanyStaff.is_active.is_(True),
                CompanyStaff.role.in_(finance_roles),
            )
            .all()
        )
        recipients.update(row[0] for row in rows if row[0])

    # An outbound sender should not receive a misleading "money received"
    # alert unless they are also the actual resolved payee.
    if (
        payment.direction.value == "outbound"
        and payment.initiated_by_user_id in recipients
        and payment.payee_phone != getattr(payment.initiated_by, "phone", None)
    ):
        recipients.discard(payment.initiated_by_user_id)

    return sorted(recipients, key=str)
