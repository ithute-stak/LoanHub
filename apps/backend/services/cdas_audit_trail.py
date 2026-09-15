from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session, joinedload

import core.audit_integrity  # noqa: F401 - ensure audit hash sealing is registered
from database.models.audit_log import AuditLog
from database.models.cdas_booking import (
    CdasAnalysisRecord,
    CdasBookingFailure,
    CdasBookingOpportunity,
    CdasOpportunityContact,
)
from database.models.company_staff import CompanyStaff
from database.models.user import User
from utils.convex import (
    current_impersonator_id,
    current_ip_address,
    current_request_id,
    current_user_agent,
    current_user_id,
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

_SENSITIVE_OR_LARGE_FIELDS = {
    "analysis_snapshot",
    "analysis_fingerprint",
    "notes",
    "reason_details",
}


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


def _role_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _actor_scope(connection, company_id: UUID | None) -> tuple[UUID | None, UUID | None, str | None]:
    actor_id = current_user_id.get()
    try:
        actor_uuid = UUID(str(actor_id)) if actor_id else None
    except (TypeError, ValueError):
        actor_uuid = None
    if not actor_uuid or not company_id:
        return actor_uuid, None, None

    membership = connection.execute(
        select(CompanyStaff.branch_id, CompanyStaff.role)
        .where(
            CompanyStaff.company_id == company_id,
            CompanyStaff.user_id == actor_uuid,
        )
        .order_by(CompanyStaff.is_active.desc(), CompanyStaff.created_at.asc())
        .limit(1)
    ).one_or_none()
    if not membership:
        return actor_uuid, None, None
    return actor_uuid, membership[0], _role_value(membership[1])


def _analysis_summary(row: CdasAnalysisRecord) -> dict[str, Any]:
    return {
        "client_name": row.client_name,
        "client_reference": row.client_reference,
        "employee_no": row.employee_no,
        "employer": row.employer,
        "current_agency_name": row.current_agency_name,
        "decision": row.decision,
        "assessed_available_amount": _safe_value(row.assessed_available_amount),
        "next_possible_booking_date": _safe_value(row.next_possible_booking_date),
        "data_quality_issue_count": int(row.data_quality_issue_count or 0),
    }


def _opportunity_summary(row: CdasBookingOpportunity) -> dict[str, Any]:
    return {
        "client_name": row.client_name,
        "client_reference": row.client_reference,
        "status": row.status,
        "pipeline_stage": row.pipeline_stage,
        "assigned_to_user_id": _safe_value(row.assigned_to_user_id),
        "booking_open_date": _safe_value(row.booking_open_date),
        "opportunity_agency_name": row.opportunity_agency_name,
        "opportunity_item_code": row.opportunity_item_code,
        "opportunity_reference_no": row.opportunity_reference_no,
        "opportunity_deduction_amount": _safe_value(row.opportunity_deduction_amount),
        "booked_at": _safe_value(row.booked_at),
        "booked_by_user_id": _safe_value(row.booked_by_user_id),
    }


def _contact_summary(row: CdasOpportunityContact) -> dict[str, Any]:
    return {
        "opportunity_id": _safe_value(row.opportunity_id),
        "channel": row.channel,
        "outcome": row.outcome,
        "contacted_at": _safe_value(row.contacted_at),
        "next_follow_up_at": _safe_value(row.next_follow_up_at),
        "has_notes": bool(row.notes),
    }


def _failure_summary(row: CdasBookingFailure) -> dict[str, Any]:
    return {
        "opportunity_id": _safe_value(row.opportunity_id),
        "reason_code": row.reason_code,
        "failed_at": _safe_value(row.failed_at),
        "retry_eligible": bool(row.retry_eligible),
        "retry_after": _safe_value(row.retry_after),
        "has_details": bool(row.reason_details),
    }


def _summary(target: Any) -> dict[str, Any]:
    if isinstance(target, CdasAnalysisRecord):
        return _analysis_summary(target)
    if isinstance(target, CdasBookingOpportunity):
        return _opportunity_summary(target)
    if isinstance(target, CdasOpportunityContact):
        return _contact_summary(target)
    if isinstance(target, CdasBookingFailure):
        return _failure_summary(target)
    return {}


def _old_value(state, field: str) -> Any:
    history = state.attrs[field].history
    if history.deleted:
        return _safe_value(history.deleted[0])
    return None


def _opportunity_action(target: CdasBookingOpportunity, changed_fields: set[str]) -> str | None:
    state = inspect(target)
    old_stage = _old_value(state, "pipeline_stage") if "pipeline_stage" in changed_fields else None
    new_stage = str(target.pipeline_stage or "").strip().lower()
    old_status = _old_value(state, "status") if "status" in changed_fields else None
    new_status = str(target.status or "").strip().lower()

    if new_stage == "failed":
        # Failure creation has its own stronger event with the reason code.
        return None
    if new_stage == "booked" or (new_status == "booked" and old_status != "booked"):
        return "CDAS_BOOKED"
    if old_stage == "failed" and new_stage and new_stage != "failed":
        return "CDAS_FAILURE_RETRIED"
    if "pipeline_stage" in changed_fields:
        return "CDAS_PIPELINE_CHANGED"
    if "assigned_to_user_id" in changed_fields:
        return "CDAS_ASSIGNMENT_CHANGED"

    business_fields = changed_fields - {
        "updated_at",
        "pipeline_updated_at",
        "pipeline_updated_by_user_id",
        "analysis_snapshot",
    }
    return "CDAS_OPPORTUNITY_SAVED" if business_fields else None


def _event_description(action: str) -> str:
    return {
        "CDAS_ANALYSIS_ARCHIVED": "CDAS analysis archived",
        "CDAS_BULK_ANALYSIS_COMPLETED": "Bulk CDAS analysis completed",
        "CDAS_OPPORTUNITY_SAVED": "CDAS booking opportunity saved",
        "CDAS_PIPELINE_CHANGED": "CDAS opportunity pipeline stage changed",
        "CDAS_ASSIGNMENT_CHANGED": "CDAS opportunity officer assignment changed",
        "CDAS_CONTACT_LOGGED": "CDAS client contact logged",
        "CDAS_FAILURE_RECORDED": "CDAS booking failure recorded",
        "CDAS_FAILURE_RETRIED": "Failed CDAS booking reopened for retry",
        "CDAS_BOOKED": "CDAS booking marked booked",
    }.get(action, "CDAS workflow event")


def _entity_type(target: Any) -> str:
    if isinstance(target, CdasAnalysisRecord):
        return "cdas_analysis"
    if isinstance(target, CdasBookingOpportunity):
        return "cdas_opportunity"
    if isinstance(target, CdasOpportunityContact):
        return "cdas_contact"
    if isinstance(target, CdasBookingFailure):
        return "cdas_failure"
    return "cdas_event"


def _formal_event(
    *,
    target: Any,
    action: str,
    before_data: dict[str, Any],
    changed_fields: list[str],
) -> dict[str, Any]:
    return {
        "target": target,
        "action": action,
        "before_data": before_data,
        "changed_fields": changed_fields,
    }


@event.listens_for(Session, "before_flush")
def capture_formal_cdas_events(session: Session, _flush_context, _instances) -> None:
    captured = session.info.setdefault("loanhub_formal_cdas_events", [])

    for target in list(session.new):
        if isinstance(target, CdasAnalysisRecord):
            captured.append(_formal_event(
                target=target,
                action="CDAS_ANALYSIS_ARCHIVED",
                before_data={},
                changed_fields=[],
            ))
        elif isinstance(target, CdasBookingOpportunity):
            captured.append(_formal_event(
                target=target,
                action="CDAS_OPPORTUNITY_SAVED",
                before_data={},
                changed_fields=[],
            ))
        elif isinstance(target, CdasOpportunityContact):
            captured.append(_formal_event(
                target=target,
                action="CDAS_CONTACT_LOGGED",
                before_data={},
                changed_fields=[],
            ))
        elif isinstance(target, CdasBookingFailure):
            captured.append(_formal_event(
                target=target,
                action="CDAS_FAILURE_RECORDED",
                before_data={},
                changed_fields=[],
            ))

    for target in list(session.dirty):
        if not isinstance(target, CdasBookingOpportunity):
            continue
        if not session.is_modified(target, include_collections=False):
            continue
        state = inspect(target)
        changed = {
            attr.key
            for attr in state.mapper.column_attrs
            if state.attrs[attr.key].history.has_changes()
        }
        action = _opportunity_action(target, changed)
        if not action:
            continue
        safe_changed = sorted(changed - _SENSITIVE_OR_LARGE_FIELDS - {"updated_at"})
        before = {
            field: _old_value(state, field)
            for field in safe_changed
            if field in state.attrs
        }
        captured.append(_formal_event(
            target=target,
            action=action,
            before_data=before,
            changed_fields=safe_changed,
        ))


@event.listens_for(Session, "after_flush_postexec")
def persist_formal_cdas_events(session: Session, _flush_context) -> None:
    captured = session.info.pop("loanhub_formal_cdas_events", [])
    if not captured:
        return

    connection = session.connection()
    for event_item in captured:
        target = event_item["target"]
        company_id = getattr(target, "company_id", None)
        if not company_id:
            continue
        actor_id, branch_id, actor_role = _actor_scope(connection, company_id)
        action = event_item["action"]
        after_data = _summary(target)
        event_row = AuditLog(
            user_id=actor_id,
            company_id=company_id,
            branch_id=branch_id,
            action=action,
            table_name="cdas",
            entity_type=_entity_type(target),
            record_id=getattr(target, "id", None),
            description=_event_description(action),
            actor_role=actor_role,
            severity="warning" if action == "CDAS_FAILURE_RECORDED" else "info",
            status="success",
            before_data=event_item["before_data"],
            after_data=after_data,
            changed_fields=event_item["changed_fields"],
            event_data={
                "formal_cdas_audit": True,
                "automatic": True,
                "impersonated_by": current_impersonator_id.get(),
            },
            request_id=current_request_id.get(),
            ip_address=current_ip_address.get(),
            user_agent=current_user_agent.get(),
        )
        session.add(event_row)


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
    """Append one explicit immutable hash-sealed CDAS business audit event."""
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
        event_data={"formal_cdas_audit": True, **_safe_value(event_data or {})},
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
    ).filter(AuditLog.action.in_(CDAS_AUDIT_ACTIONS))
