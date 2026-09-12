from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from core.access_control import require_platform_admin
from database.models.audit_log import AuditLog
from database.models.system_error import SystemErrorLog
from database.models.user import User
from database.schemas.system_error import (
    SystemErrorListRead,
    SystemErrorRead,
    SystemErrorResolveCreate,
)
from database.session import get_db


router = APIRouter(
    prefix="/system-errors",
    tags=["System Error Monitoring"],
)


def error_or_404(db: Session, error_id: UUID) -> SystemErrorLog:
    error_log = (
        db.query(SystemErrorLog)
        .filter(SystemErrorLog.id == error_id)
        .first()
    )
    if not error_log:
        raise HTTPException(
            status_code=404,
            detail="System error not found",
        )
    return error_log


def add_resolution_audit(
    db: Session,
    *,
    error_log: SystemErrorLog,
    current_user: User,
    action: str,
    before_resolved: bool,
) -> None:
    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=error_log.company_id,
            branch_id=error_log.branch_id,
            action=action,
            table_name="system_error_logs",
            entity_type="system_error_logs",
            record_id=error_log.id,
            description=(
                "A platform administrator resolved a system error."
                if action == "resolved"
                else "A platform administrator reopened a system error."
            ),
            actor_role=current_user.role.value,
            severity="warning",
            status="success",
            before_data={"is_resolved": before_resolved},
            after_data={
                "is_resolved": error_log.is_resolved,
                "resolved_at": (
                    str(error_log.resolved_at)
                    if error_log.resolved_at
                    else None
                ),
                "resolution_notes": error_log.resolution_notes,
            },
            changed_fields=[
                "is_resolved",
                "resolved_at",
                "resolved_by_user_id",
                "resolution_notes",
            ],
            event_data={"automatic": False},
        )
    )


@router.get("", response_model=SystemErrorListRead)
def list_system_errors(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    unresolved_only: bool = False,
    severity: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    query = db.query(SystemErrorLog)

    if unresolved_only:
        query = query.filter(
            SystemErrorLog.is_resolved.is_(False)
        )
    if severity:
        query = query.filter(
            SystemErrorLog.severity == severity
        )
    if search:
        token = f"%{search.strip()}%"
        query = query.filter(
            or_(
                SystemErrorLog.path.ilike(token),
                SystemErrorLog.error_type.ilike(token),
                SystemErrorLog.message.ilike(token),
                SystemErrorLog.request_id.ilike(token),
            )
        )

    total = query.count()
    unresolved_count = (
        db.query(func.count(SystemErrorLog.id))
        .filter(SystemErrorLog.is_resolved.is_(False))
        .scalar()
        or 0
    )
    items = (
        query.order_by(SystemErrorLog.last_seen_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return SystemErrorListRead(
        items=[
            SystemErrorRead.model_validate(item)
            for item in items
        ],
        total=total,
        unresolved_count=unresolved_count,
        page=page,
        page_size=page_size,
    )


@router.patch(
    "/{error_id}/resolve",
    response_model=SystemErrorRead,
)
def resolve_system_error(
    error_id: UUID,
    payload: SystemErrorResolveCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_admin),
):
    error_log = error_or_404(db, error_id)
    before_resolved = error_log.is_resolved

    error_log.is_resolved = True
    error_log.resolved_at = datetime.utcnow()
    error_log.resolved_by_user_id = current_user.id
    error_log.resolution_notes = payload.resolution_notes

    add_resolution_audit(
        db,
        error_log=error_log,
        current_user=current_user,
        action="resolved",
        before_resolved=before_resolved,
    )

    db.commit()
    db.refresh(error_log)
    return error_log


@router.patch(
    "/{error_id}/reopen",
    response_model=SystemErrorRead,
)
def reopen_system_error(
    error_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_admin),
):
    error_log = error_or_404(db, error_id)
    before_resolved = error_log.is_resolved

    error_log.is_resolved = False
    error_log.resolved_at = None
    error_log.resolved_by_user_id = None
    error_log.resolution_notes = None

    add_resolution_audit(
        db,
        error_log=error_log,
        current_user=current_user,
        action="reopened",
        before_resolved=before_resolved,
    )

    db.commit()
    db.refresh(error_log)
    return error_log
