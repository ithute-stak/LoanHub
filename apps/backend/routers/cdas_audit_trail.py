from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.models.audit_log import AuditLog
from database.session import get_db
from services.cdas_audit_trail import (
    CDAS_AUDIT_ACTIONS,
    cdas_audit_query,
    serialize_cdas_audit_event,
)

router = APIRouter(prefix="/cdas-booking", tags=["CDAS Formal Audit Trail"])


def _require_company_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")


@router.get("/audit-trail")
def get_cdas_audit_trail(
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    actor_user_id: UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Return immutable, hash-sealed CDAS business events for the active company."""
    _require_company_member(context)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="Audit start date cannot be after end date")

    normalized_action = str(action or "").strip().upper() or None
    if normalized_action and normalized_action not in CDAS_AUDIT_ACTIONS:
        raise HTTPException(status_code=422, detail="Unsupported CDAS audit action")

    query = cdas_audit_query(db).filter(AuditLog.company_id == context.company_id)
    if normalized_action:
        query = query.filter(AuditLog.action == normalized_action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type.strip().lower())
    if actor_user_id:
        query = query.filter(AuditLog.user_id == actor_user_id)
    if date_from:
        query = query.filter(AuditLog.created_at >= date_from)
    if date_to:
        query = query.filter(AuditLog.created_at <= date_to)
    if search and search.strip():
        token = f"%{search.strip()}%"
        query = query.filter(
            or_(
                AuditLog.description.ilike(token),
                AuditLog.entity_type.ilike(token),
                AuditLog.actor_role.ilike(token),
            )
        )

    total = query.count()
    rows = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    option_rows = cdas_audit_query(db).filter(
        AuditLog.company_id == context.company_id
    ).order_by(AuditLog.created_at.desc()).limit(1000).all()
    actions = sorted({row.action for row in option_rows if row.action})
    entity_types = sorted({row.entity_type for row in option_rows if row.entity_type})
    actors: dict[str, dict] = {}
    for row in option_rows:
        if not row.user_id:
            continue
        serialized = serialize_cdas_audit_event(row)
        actors[str(row.user_id)] = {
            "user_id": str(row.user_id),
            "name": serialized.get("actor_name") or "Company staff",
            "role": row.actor_role,
        }

    sealed_count = sum(1 for row in option_rows if row.event_hash and row.sealed_at)
    return {
        "items": [serialize_cdas_audit_event(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "summary": {
            "formal_events_sampled": len(option_rows),
            "sealed_events_sampled": sealed_count,
            "unsealed_events_sampled": len(option_rows) - sealed_count,
        },
        "options": {
            "actions": actions,
            "entity_types": entity_types,
            "actors": sorted(actors.values(), key=lambda item: item["name"].casefold()),
        },
    }
