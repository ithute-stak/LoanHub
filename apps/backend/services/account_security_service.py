from __future__ import annotations

from typing import Iterable

from fastapi import Request
from sqlalchemy.orm import Session

from database.models.audit_log import AuditLog
from database.models.user import User


def client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()[:100]
    return request.client.host[:100] if request.client else None


def record_account_event(
    db: Session,
    *,
    user: User | None,
    request: Request | None,
    action: str,
    description: str,
    status: str = "success",
    severity: str = "info",
    changed_fields: Iterable[str] = (),
    event_data: dict | None = None,
) -> AuditLog:
    event = AuditLog(
        user_id=user.id if user else None,
        action=action,
        table_name="users",
        entity_type="account_security",
        record_id=user.id if user else None,
        description=description,
        actor_role=user.role.value if user else None,
        severity=severity,
        status=status,
        changed_fields=list(changed_fields),
        event_data=event_data or {},
        ip_address=client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:500] or None if request else None,
    )
    db.add(event)
    return event
