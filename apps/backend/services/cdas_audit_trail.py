from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from database.models.audit_log import AuditLog
from database.models.user import User
from utils.convex import (
    current_ip_address,
    current_request_id,
    current_user_agent,
)

CDAS_AUDIT_ACTIONS = (
    "CDAS_ANALYSIS_ARCHIVED",
    "CDAS_BULK_ANALYSIS_COMPLETED",
    "CDAS_OPPORTUNITY_SAVED",
    "CDAS_PIPELINE_CHANGED",
    "CDAS_ASSIGNMENT_CHANGED",
    "CDAS_CONTACT_LOGGED",
    "CDAS_FAILURE_RECORDED",
    "CDAS_FAILURE_RETRIED",
    "CDAS_BOOKED",
)


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (UUID, date, datetime)):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(key): _safe_value(child) for key, child in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_value(child) for child in value]
    return str(value)


def append_cdas_audit_event(
    db: Session,
    *,
    user_id: UUID | None,
    company_id: UUID,
    branch_id: UUID | None,
    actor_role: str | None,
    action: str,
    entity_type: str,
    record_id: UUID | None,
    description: str,
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
    changed_fields: list[str] | None = None,
    event_data: dict[str, Any] | None = None,
    severity: str = "info",
) -> AuditLog:
    """Append one immutable hash-sealed CDAS business audit event.

    Callers deliberately pass small structured summaries. Raw pasted CDAS text,
    full analysis snapshots, contact notes and free-form failure details must not
    be supplied here.
    """
    normalized_action = str(action or "").strip().upper()
    if normalized_action not in CDAS_AUDIT_ACTIONS:
        raise ValueError("Unsupported CDAS audit action")

    row = AuditLog(
        user_id=user_id,
        company_id=company_id,
        branch_id=branch_id,
        action=normalized_action,
        table_name="cdas",
        entity_type=str(entity_type or "cdas_event").strip().lower(),
        record_id=record_id,
        description=str(description or "CDAS workflow event").strip(),
        actor_role=(actor_role or "").strip() or None,
        severity=str(severity or "info").strip().lower(),
        status="success",
        before_data=_safe_value(before_data or {}),
        after_data=_safe_value(after_data or {}),
        changed_fields=[str(value) for value in (changed_fields or [])],
        event_data={
            "formal_cdas_audit": True,
            **_safe_value(event_data or {}),
        },
        request_id=current_request_id.get(),
        ip_address=current_ip_address.get(),
        user_agent=current_user_agent.get(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _actor_name(row: AuditLog) -> str | None:
    user = row.user
    if not user:
        return None
    person = getattr(user, "person", None)
    name = str(getattr(person, "full_name", "") or "").strip()
    return name or str(user.email or user.phone or "").strip() or None


def serialize_cdas_audit_event(row: AuditLog) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "timestamp": row.created_at.isoformat() if row.created_at else None,
        "user_id": str(row.user_id) if row.user_id else None,
        "actor_name": _actor_name(row),
        "actor_role": row.actor_role,
        "action": row.action,
        "entity_type": row.entity_type,
        "record_id": str(row.record_id) if row.record_id else None,
        "description": row.description,
        "severity": row.severity,
        "before_data": row.before_data or {},
        "after_data": row.after_data or {},
        "changed_fields": row.changed_fields or [],
        "event_data": row.event_data or {},
        "request_id": row.request_id,
        "integrity": {
            "sealed": bool(row.event_hash and row.sealed_at),
            "hash_version": row.hash_version,
            "previous_hash": row.previous_hash,
            "event_hash": row.event_hash,
            "sealed_at": row.sealed_at.isoformat() if row.sealed_at else None,
        },
    }


def cdas_audit_query(db: Session):
    return db.query(AuditLog).options(
        joinedload(AuditLog.user).joinedload(User.person),
    ).filter(
        AuditLog.action.in_(CDAS_AUDIT_ACTIONS),
        AuditLog.event_data["formal_cdas_audit"].as_boolean().is_(True),
    )
