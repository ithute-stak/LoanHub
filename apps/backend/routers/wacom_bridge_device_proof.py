"""First-party, per-employee Wacom workstation possession checks.

Never issues a bridge bearer token, capture ticket, or signing authorization.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.access_control import LENDING_ROLES, TenantContext, get_tenant_context, require_tenant_roles
from database.models.wacom_bridge_challenge import WacomBridgeChallenge
from database.models.wacom_bridge_session import WacomBridgeSession
from database.models.wacom_workstation import WacomWorkstationEnrollment
from database.models.wacom_workstation_operator import WacomWorkstationOperator
from database.session import get_db
from services.wacom_bridge_device_proof import proof_message, verify_device_proof
from services.wacom_bridge_sessions import issue_bridge_session

router = APIRouter(prefix="/wacom-bridge", tags=["Wacom First-party Device Proof"])


class BridgeChallengeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workstation_id: UUID


class BridgeProofRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge_id: UUID
    workstation_id: UUID
    signature_base64: str = Field(min_length=86, max_length=88)


def _eligible_device(db: Session, ctx: TenantContext, workstation_id: UUID):
    require_tenant_roles(ctx, LENDING_ROLES)
    pc = db.query(WacomWorkstationEnrollment).filter(
        WacomWorkstationEnrollment.company_id == ctx.company_id,
        WacomWorkstationEnrollment.workstation_id == workstation_id,
        WacomWorkstationEnrollment.status == "active",
        WacomWorkstationEnrollment.approved_at.is_not(None),
        WacomWorkstationEnrollment.revoked_at.is_(None),
    ).one_or_none()
    if pc is None:
        raise HTTPException(403, "No active approved Wacom workstation")
    assignment = db.query(WacomWorkstationOperator).filter(
        WacomWorkstationOperator.company_id == ctx.company_id,
        WacomWorkstationOperator.workstation_id == workstation_id,
        WacomWorkstationOperator.employee_user_id == ctx.user.id,
        WacomWorkstationOperator.status == "active",
        WacomWorkstationOperator.revoked_at.is_(None),
    ).one_or_none()
    if assignment is None:
        raise HTTPException(403, "Employee not assigned to this workstation")
    return pc


@router.post("/device-challenges", status_code=201)
def create_device_challenge(
    body: BridgeChallengeRequest, response: Response,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    pc = _eligible_device(db, ctx, body.workstation_id)
    now = datetime.now(timezone.utc)
    outstanding = db.query(func.count(WacomBridgeChallenge.id)).filter(
        WacomBridgeChallenge.company_id == ctx.company_id,
        WacomBridgeChallenge.employee_user_id == ctx.user.id,
        WacomBridgeChallenge.workstation_id == body.workstation_id,
        WacomBridgeChallenge.consumed_at.is_(None),
        WacomBridgeChallenge.expires_at > now,
    ).scalar()
    if outstanding is None or outstanding >= 3:
        raise HTTPException(429, "Too many active workstation challenges")
    challenge = WacomBridgeChallenge(
        id=uuid4(), company_id=ctx.company_id,
        employee_user_id=ctx.user.id, workstation_id=pc.workstation_id,
        nonce=secrets.token_bytes(32), expires_at=now + timedelta(seconds=30),
    )
    db.add(challenge)
    db.commit()
    return {
        "challenge_id": str(challenge.id),
        "workstation_id": str(challenge.workstation_id),
        "company_id": str(ctx.company_id),
        "employee_user_id": str(ctx.user.id),
        "nonce": base64.urlsafe_b64encode(challenge.nonce).decode("ascii").rstrip("="),
        "expires_at": challenge.expires_at.isoformat(),
        "device_proof_required": True,
        "signing_authorized": False,
    }


@router.post("/device-proofs")
def verify_bridge_device_proof(
    body: BridgeProofRequest, response: Response,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    pc = _eligible_device(db, ctx, body.workstation_id)
    row = db.query(WacomBridgeChallenge).filter(
        WacomBridgeChallenge.id == body.challenge_id,
        WacomBridgeChallenge.company_id == ctx.company_id,
        WacomBridgeChallenge.employee_user_id == ctx.user.id,
        WacomBridgeChallenge.workstation_id == body.workstation_id,
    ).with_for_update().one_or_none()
    now = datetime.now(timezone.utc)
    if row is None or row.consumed_at is not None or now >= row.expires_at:
        raise HTTPException(409, "Workstation challenge unavailable or expired")
    try:
        signature = base64.b64decode(body.signature_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(422, "Malformed workstation proof") from exc
    message = proof_message(
        company_id=ctx.company_id, employee_id=ctx.user.id,
        workstation_id=body.workstation_id, challenge_id=row.id,
        nonce=bytes(row.nonce), expires_at=row.expires_at,
    )
    verify_device_proof(public_key=bytes(pc.ed25519_public_key),
                        signature=signature, message=message)
    row.consumed_at = now
    token, session_row = issue_bridge_session(
        db, context=ctx, workstation_id=body.workstation_id,
    )
    db.commit()
    return {
        "device_proof_verified": True,
        "bridge_session_token": token,
        "bridge_session_expires_at": session_row.expires_at.isoformat(),
        "employee_user_id": str(ctx.user.id),
        "workstation_id": str(body.workstation_id),
        "bridge_session_authorized": True,
        "capture_authorized": False,
        "contract_signed": False,
    }


# Revocation is based on the authenticated LoanHub user plus the exact
# session credential. A stolen session alone cannot revoke a different user.
_SESSION_RE = re.compile(r"^wb1_[A-Za-z0-9_-]{43}$")


@router.post("/sessions/revoke")
def revoke_bridge_session(
    response: Response,
    x_wacom_bridge_session: str | None = Header(default=None, alias="X-Wacom-Bridge-Session"),
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    if x_wacom_bridge_session is None or not _SESSION_RE.fullmatch(x_wacom_bridge_session):
        raise HTTPException(403, "Verified workstation session required")
    if ctx.company_id is None or ctx.staff is None:
        raise HTTPException(403, "Active company membership required")
    digest = hashlib.sha256(x_wacom_bridge_session.encode("ascii")).digest()
    row = db.query(WacomBridgeSession).filter(
        WacomBridgeSession.company_id == ctx.company_id,
        WacomBridgeSession.employee_user_id == ctx.user.id,
        WacomBridgeSession.token_sha256 == digest,
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(403, "Workstation session unavailable")
    # Idempotent: an already-revoked credential never becomes valid again.
    if row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return {"revoked": True, "signing_authorized": False}
