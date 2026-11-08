"""Tenant-admin controlled Wacom workstation registration and approval.

A registration records only a workstation's *public* Ed25519 key and starts
pending. A different company administrator must approve it. No route issues
capture tickets, signs contracts or accepts handwriting.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES, LENDING_ROLES, TenantContext,
    get_user_context, require_tenant_roles,
)
from database.models.wacom_workstation import WacomWorkstationEnrollment
from database.session import get_db
from database.models.wacom_bridge_session import WacomBridgeSession

router = APIRouter(prefix="/contract-signing/workstations", tags=["Wacom Workstation Enrollment"])

class WorkstationRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workstation_id: UUID
    ed25519_public_key_base64: str = Field(min_length=43, max_length=44)


def _key(value: str) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(422, "Invalid workstation public key") from error
    if len(decoded) != 32 or base64.b64encode(decoded).decode("ascii") != value:
        raise HTTPException(422, "Expected canonical Base64 Ed25519 public key")
    return decoded


def _scoped_enrollment(db: Session, context: TenantContext, enrollment_id: UUID):
    row = (
        db.query(WacomWorkstationEnrollment)
        .filter(
            WacomWorkstationEnrollment.id == enrollment_id,
            WacomWorkstationEnrollment.company_id == context.company_id,
        )
        .with_for_update()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(404, "Workstation enrollment unavailable")
    return row


@router.post("", status_code=201)
def register_wacom_workstation(
    payload: WorkstationRegistration,
    response: Response,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """An authenticated operator proposes a key; enrollment is not yet trusted."""
    require_tenant_roles(context, LENDING_ROLES | COMPANY_MANAGEMENT_ROLES)
    response.headers["Cache-Control"] = "no-store"
    if context.company_id is None:
        raise HTTPException(403, "Tenant company is required")
    row = WacomWorkstationEnrollment(
        id=uuid4(), company_id=context.company_id,
        operator_user_id=context.user.id, workstation_id=payload.workstation_id,
        ed25519_public_key=_key(payload.ed25519_public_key_base64),
        status="pending", created_by=str(context.user.id),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Workstation already registered for this company") from error
    return {
        "enrollment_id": str(row.id),
        "workstation_id": str(row.workstation_id),
        "status": "pending",
        "capture_enabled": False,
    }


@router.post("/{enrollment_id}/approve")
def approve_wacom_workstation(
    enrollment_id: UUID,
    response: Response,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Manager approval cannot be performed by the original registrant."""
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    response.headers["Cache-Control"] = "no-store"
    row = _scoped_enrollment(db, context, enrollment_id)
    if row.status != "pending" or row.approved_at is not None or row.revoked_at is not None:
        raise HTTPException(409, "Workstation enrollment cannot be approved")
    if row.operator_user_id == context.user.id or row.created_by == str(context.user.id):
        raise HTTPException(403, "A different company administrator must approve enrollment")
    row.status = "active"
    row.approved_at = datetime.now(timezone.utc)
    row.updated_by = str(context.user.id)
    db.commit()
    return {
        "enrollment_id": str(row.id),
        "status": "active",
        "capture_enabled": False,
    }


@router.post("/{enrollment_id}/revoke")
def revoke_wacom_workstation(
    enrollment_id: UUID,
    response: Response,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Revocation is permanent for the current enrollment and public key."""
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    response.headers["Cache-Control"] = "no-store"
    row = _scoped_enrollment(db, context, enrollment_id)
    if row.status not in ("pending", "active") or row.revoked_at is not None:
        raise HTTPException(409, "Workstation enrollment already closed")
    row.status = "revoked"
    row.revoked_at = datetime.now(timezone.utc)
    # All operator sessions on this workstation become invalid in the
    # enrollment revocation transaction, not merely after TTL expiry.
    db.query(WacomBridgeSession).filter(
        WacomBridgeSession.company_id == context.company_id,
        WacomBridgeSession.workstation_id == row.workstation_id,
        WacomBridgeSession.revoked_at.is_(None),
    ).update({WacomBridgeSession.revoked_at: row.revoked_at}, synchronize_session=False)
    row.updated_by = str(context.user.id)
    db.commit()
    return {
        "enrollment_id": str(row.id),
        "status": "revoked",
        "capture_enabled": False,
    }
