"""Company-admin-managed operators on approved, shared Wacom workstations.

Assignment records alone are never sufficient for bridge access. Protected
operations must additionally verify the personally authenticated operator's
current session and an enrolled-device proof.
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES, LENDING_ROLES, TenantContext,
    get_tenant_context, require_tenant_roles,
)
from database.models.company_staff import CompanyStaff
from database.models.user import User
from database.models.wacom_workstation import WacomWorkstationEnrollment
from database.models.wacom_workstation_operator import WacomWorkstationOperator
from database.models.audit_log import AuditLog
from database.session import get_db
from database.models.wacom_bridge_session import WacomBridgeSession

router = APIRouter(prefix="/contract-signing/workstations", tags=["Wacom Workstation Operators"])


class OperatorAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_user_id: UUID


def _approved_pc(db: Session, ctx: TenantContext, workstation_id: UUID):
    pc = db.query(WacomWorkstationEnrollment).filter(
        WacomWorkstationEnrollment.company_id == ctx.company_id,
        WacomWorkstationEnrollment.workstation_id == workstation_id,
        WacomWorkstationEnrollment.status == "active",
        WacomWorkstationEnrollment.approved_at.is_not(None),
        WacomWorkstationEnrollment.revoked_at.is_(None),
    ).one_or_none()
    if pc is None:
        raise HTTPException(404, "Approved workstation unavailable")
    return pc


def _eligible_staff(db: Session, ctx: TenantContext, user_id: UUID):
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True),
                                 User.must_change_password.is_(False)).one_or_none()
    if user is None:
        raise HTTPException(404, "Eligible employee unavailable")
    rows = db.query(CompanyStaff).filter(
        CompanyStaff.company_id == ctx.company_id,
        CompanyStaff.user_id == user_id,
        CompanyStaff.is_active.is_(True),
    ).all()
    qualifying = [s for s in rows if s.role in LENDING_ROLES]
    if not qualifying:
        raise HTTPException(403, "Employee lacks lending-company permission")
    return qualifying


def _audit(db, ctx, workstation_id, employee_id, action):
    db.add(AuditLog(
        company_id=ctx.company_id, user_id=ctx.user.id,
        branch_id=ctx.branch_id, action=action,
        table_name="wacom_workstation_operators",
        entity_type="workstation_access", status="success",
        description="Wacom workstation employee authorization changed",
        event_data={
            "workstation_id": str(workstation_id),
            "employee_user_id": str(employee_id),
            "grants_signing": False,
        },
    ))


@router.post("/{workstation_id}/operators", status_code=201)
def assign_operator(
    workstation_id: UUID, payload: OperatorAssignmentRequest,
    response: Response,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    require_tenant_roles(ctx, COMPANY_MANAGEMENT_ROLES)
    _approved_pc(db, ctx, workstation_id)
    _eligible_staff(db, ctx, payload.employee_user_id)
    existing = db.query(WacomWorkstationOperator).filter(
        WacomWorkstationOperator.company_id == ctx.company_id,
        WacomWorkstationOperator.workstation_id == workstation_id,
        WacomWorkstationOperator.employee_user_id == payload.employee_user_id,
    ).with_for_update().one_or_none()
    if existing:
        raise HTTPException(409, "Employee assignment already exists; revoked assignments require a new enrollment process")
    now = datetime.now(timezone.utc)
    db.add(WacomWorkstationOperator(
        company_id=ctx.company_id,
        workstation_id=workstation_id,
        employee_user_id=payload.employee_user_id,
        branch_id=None,
        status="active", granted_by=ctx.user.id, granted_at=now,
    ))
    _audit(db, ctx, workstation_id, payload.employee_user_id, "wacom_workstation.operator_assigned")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Employee assignment already exists") from exc
    return {"status": "active", "employee_user_id": str(payload.employee_user_id),
            "workstation_id": str(workstation_id),
            "bridge_session_authorized": False, "signing_authorized": False}


@router.get("/{workstation_id}/operators")
def list_operators(
    workstation_id: UUID, response: Response,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    require_tenant_roles(ctx, COMPANY_MANAGEMENT_ROLES)
    _approved_pc(db, ctx, workstation_id)
    rows = db.query(WacomWorkstationOperator).filter(
        WacomWorkstationOperator.company_id == ctx.company_id,
        WacomWorkstationOperator.workstation_id == workstation_id,
    ).order_by(WacomWorkstationOperator.granted_at).all()
    return {"operators": [
        {"employee_user_id": str(row.employee_user_id), "status": row.status}
        for row in rows
    ], "signing_authorized": False}


@router.post("/{workstation_id}/operators/{employee_id}/revoke")
def revoke_operator(
    workstation_id: UUID, employee_id: UUID, response: Response,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    require_tenant_roles(ctx, COMPANY_MANAGEMENT_ROLES)
    row = db.query(WacomWorkstationOperator).filter(
        WacomWorkstationOperator.company_id == ctx.company_id,
        WacomWorkstationOperator.workstation_id == workstation_id,
        WacomWorkstationOperator.employee_user_id == employee_id,
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(404, "Employee assignment unavailable")
    if row.status != "active":
        raise HTTPException(409, "Employee assignment is not active")
    row.status = "revoked"
    row.revoked_by = ctx.user.id
    row.revoked_at = datetime.now(timezone.utc)
    # Invalidate every outstanding token for this employee on this PC in
    # the SAME transaction as assignment revocation.
    db.query(WacomBridgeSession).filter(
        WacomBridgeSession.company_id == ctx.company_id,
        WacomBridgeSession.workstation_id == workstation_id,
        WacomBridgeSession.employee_user_id == employee_id,
        WacomBridgeSession.revoked_at.is_(None),
    ).update({WacomBridgeSession.revoked_at: row.revoked_at}, synchronize_session=False)
    _audit(db, ctx, workstation_id, employee_id, "wacom_workstation.operator_revoked")
    db.commit()
    return {"status": "revoked", "bridge_session_authorized": False, "signing_authorized": False}


@router.get("/{workstation_id}/my-assignment")
def my_assignment(
    workstation_id: UUID, response: Response,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    require_tenant_roles(ctx, LENDING_ROLES)
    _approved_pc(db, ctx, workstation_id)
    _eligible_staff(db, ctx, ctx.user.id)
    row = db.query(WacomWorkstationOperator).filter(
        WacomWorkstationOperator.company_id == ctx.company_id,
        WacomWorkstationOperator.workstation_id == workstation_id,
        WacomWorkstationOperator.employee_user_id == ctx.user.id,
        WacomWorkstationOperator.status == "active",
        WacomWorkstationOperator.revoked_at.is_(None),
    ).one_or_none()
    if row is None:
        raise HTTPException(403, "This operator is not assigned to the workstation")
    return {"assigned": True, "workstation_id": str(workstation_id),
            "operator_id": str(ctx.user.id),
            "bridge_session_authorized": False, "device_proof_required": True,
            "signing_authorized": False}
