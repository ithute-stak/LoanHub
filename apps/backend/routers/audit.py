
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from core.access_control import (
    COMPANY_ROLES,
    TRANSPARENCY_ROLES,
    get_current_active_user,
    resolve_tenant_context,
)
from database.models.audit_log import AuditLog
from database.models.enums import UserRole
from database.models.user import User
from database.schemas.audit import AuditLogListRead, AuditLogRead
from database.session import get_db


router = APIRouter(prefix="/audit", tags=["Audit and Transparency"])


def human_reference(item: AuditLog) -> str:
    data = item.after_data or item.before_data or {}
    for key in (
        "reference",
        "loan_reference",
        "employee_number",
        "entry_number",
        "provider_reference",
        "name",
        "title",
        "code",
    ):
        value = data.get(key)
        if value:
            return str(value)

    token = str(item.record_id or item.id).replace("-", "")[-8:].upper()
    year = item.created_at.year if item.created_at else 0
    prefix = (item.entity_type or item.table_name or "event")[:3].upper()
    return f"{prefix}-{year}-{token}"


def audit_read(item: AuditLog) -> AuditLogRead:
    actor_name = None
    if item.user:
        actor_name = (
            item.user.person.full_name
            if item.user.person
            else item.user.email or item.user.phone
        )

    return AuditLogRead.model_validate(item).model_copy(
        update={
            "actor_name": actor_name,
            "company_name": item.company.name if item.company else None,
            "branch_name": item.branch.name if item.branch else None,
            "entity_reference": human_reference(item),
        }
    )


@router.get("/events", response_model=AuditLogListRead)
def list_audit_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    action: str | None = None,
    entity_type: str | None = None,
    search: str | None = None,
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    x_active_role: str | None = Header(default=None, alias="X-Active-Role"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(AuditLog).options(
        joinedload(AuditLog.user).joinedload(User.person),
        joinedload(AuditLog.company),
        joinedload(AuditLog.branch),
    )

    if current_user.role == UserRole.SUPERADMIN:
        pass
    elif current_user.role == UserRole.BORROWER:
        query = query.filter(AuditLog.user_id == current_user.id)
    elif current_user.role in COMPANY_ROLES:
        context = resolve_tenant_context(db, current_user, x_company_id, x_active_role)
        if context.role not in TRANSPARENCY_ROLES:
            raise HTTPException(status_code=403, detail="Transparency access is not assigned to this role")
        query = query.filter(AuditLog.company_id == context.company_id)
        if context.branch_id and context.role not in {
            UserRole.COMPANY_OWNER,
            UserRole.COMPANY_ADMIN,
            UserRole.AUDITOR,
            UserRole.COMPLIANCE_OFFICER,
        }:
            query = query.filter(
                or_(
                    AuditLog.branch_id == context.branch_id,
                    AuditLog.branch_id.is_(None),
                )
            )
    else:
        raise HTTPException(status_code=403, detail="Audit access is not available")

    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if search:
        token = f"%{search.strip()}%"
        query = query.filter(
            or_(
                AuditLog.description.ilike(token),
                AuditLog.table_name.ilike(token),
                AuditLog.actor_role.ilike(token),
            )
        )

    total = query.count()
    items = (
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return AuditLogListRead(
        items=[audit_read(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
