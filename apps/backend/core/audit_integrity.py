from __future__ import annotations

import hashlib
import json
from datetime import date, datetime

from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from database.models.audit_log import AuditLog


GENESIS_HASH = "0" * 64


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def canonical_audit_payload(item: AuditLog, previous_hash: str) -> bytes:
    payload = {
        "action": item.action,
        "actor_role": item.actor_role,
        "after_data": item.after_data or {},
        "before_data": item.before_data or {},
        "branch_id": str(item.branch_id) if item.branch_id else None,
        "changed_fields": item.changed_fields or [],
        "company_id": str(item.company_id) if item.company_id else None,
        "description": item.description,
        "entity_type": item.entity_type,
        "event_data": item.event_data or {},
        "previous_hash": previous_hash,
        "record_id": str(item.record_id) if item.record_id else None,
        "request_id": item.request_id,
        "severity": item.severity,
        "status": item.status,
        "table_name": item.table_name,
        "user_id": str(item.user_id) if item.user_id else None,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default).encode()


def audit_hash(item: AuditLog, previous_hash: str) -> str:
    return hashlib.sha256(canonical_audit_payload(item, previous_hash)).hexdigest()


@event.listens_for(Session, "before_flush")
def seal_audit_events(session: Session, _flush_context, _instances) -> None:
    for item in tuple(session.deleted) + tuple(session.dirty):
        if isinstance(item, AuditLog) and item.event_hash:
            raise ValueError("Sealed audit events are immutable")

    pending = [item for item in session.new if isinstance(item, AuditLog) and not item.event_hash]
    if not pending:
        return

    connection = session.connection()
    if connection.dialect.name == "postgresql":
        connection.execute(select(func.pg_advisory_xact_lock(519234781)))

    previous = session.query(AuditLog.event_hash).filter(AuditLog.event_hash.isnot(None)).order_by(AuditLog.sealed_at.desc(), AuditLog.id.desc()).limit(1).scalar() or GENESIS_HASH
    for item in pending:
        item.previous_hash = previous
        item.hash_version = "sha256-v1"
        item.event_hash = audit_hash(item, previous)
        item.sealed_at = datetime.utcnow()
        previous = item.event_hash


def verify_chain(items: list[AuditLog]) -> tuple[bool, str | None]:
    previous = GENESIS_HASH
    for item in items:
        if item.previous_hash != previous or item.event_hash != audit_hash(item, previous):
            return False, str(item.id)
        previous = item.event_hash
    return True, None
