"""Gated Ed25519 workstation-key proof for a Wacom signing ceremony.

This does not attest actual pen contact, borrower consent or legal execution.
The challenge remains PENDING; no contract, authorization or receipt execution
state is modified. Physical STU-540 certification remains mandatory.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import os
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.models.audit_log import AuditLog
from database.models.wacom_execution_ceremony_challenge import WacomExecutionCeremonyChallenge
from database.models.wacom_execution_authorization import WacomExecutionAuthorization
from database.models.wacom_execution_receipt import WacomExecutionReceipt
from database.session import get_db
from routers.wacom_bridge_device_proof import _eligible_device
from services.wacom_bridge_sessions import authorize_bridge_session
from services.wacom_ceremony_workstation_proof import verify_ceremony_workstation_proof

FEATURE_FLAG = "LOANHUB_WACOM_CEREMONY_WORKSTATION_PROOF_ENABLED"


def _gate():
    if os.getenv(FEATURE_FLAG, "") != "1":
        raise HTTPException(503, "Wacom ceremony workstation proof disabled")


router = APIRouter(
    prefix="/wacom-execution-ceremonies",
    tags=["Wacom Ceremony Workstation Key Proof"],
    dependencies=[Depends(_gate)],
)


class WorkstationProofBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workstation_id: UUID
    challenge_secret: str = Field(min_length=64, max_length=64, pattern=r"^[A-Za-z0-9_-]{64}$")
    signature_base64: str = Field(min_length=88, max_length=88)


@router.post("/challenges/{challenge_id}/workstation-proof")
def verify_workstation_key(
    challenge_id: UUID,
    body: WorkstationProofBody,
    response: Response,
    x_wacom_bridge_session: str | None = Header(default=None, alias="X-Wacom-Bridge-Session"),
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    # Normal LoanHub staff login AND independently verified PC bridge session.
    authorize_bridge_session(
        db, context=ctx, token=x_wacom_bridge_session,
    )
    enrollment = _eligible_device(db, ctx, body.workstation_id)
    row = db.query(WacomExecutionCeremonyChallenge).filter(
        WacomExecutionCeremonyChallenge.id == challenge_id,
        WacomExecutionCeremonyChallenge.company_id == ctx.company_id,
        WacomExecutionCeremonyChallenge.workstation_id == body.workstation_id,
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(404, "Ceremony challenge unavailable")
    # An issued challenge belongs to a separate management requester.
    if ctx.user.id == row.requested_by or row.workstation_proof_at is not None:
        raise HTTPException(409, "Workstation proof already supplied or not independent")
    authorization = db.query(WacomExecutionAuthorization).filter(
        WacomExecutionAuthorization.id == row.authorization_id,
        WacomExecutionAuthorization.company_id == ctx.company_id,
    ).with_for_update().one_or_none()
    receipt = db.query(WacomExecutionReceipt).filter(
        WacomExecutionReceipt.id == row.receipt_id,
        WacomExecutionReceipt.company_id == ctx.company_id,
    ).with_for_update().one_or_none()
    if (authorization is None or receipt is None
            or authorization.status != "approved" or authorization.consumed_at is not None
            or receipt.status != "reserved" or receipt.executed_at is not None
            or receipt.contract_id != row.contract_id
            or receipt.intent_id != row.intent_id
            or receipt.authorization_id != authorization.id
            or receipt.executed_pdf_sha256 != row.candidate_sha256
            or authorization.field_binding_sha256 != row.field_binding_sha256):
        raise HTTPException(409, "Ceremony evidence or authorization no longer valid")
    try:
        signature = base64.b64decode(body.signature_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(422, "Malformed workstation signature") from exc
    now = datetime.now(timezone.utc)
    digest = verify_ceremony_workstation_proof(
        challenge=row, challenge_secret=body.challenge_secret,
        operator_id=ctx.user.id, enrollment=enrollment,
        signature=signature, now=now,
    )
    row.workstation_proof_at = now
    row.workstation_proof_by = ctx.user.id
    row.workstation_proof_sha256 = digest.hex()
    db.add(AuditLog(
        user_id=ctx.user.id, company_id=ctx.company_id, branch_id=ctx.branch_id,
        action="wacom.ceremony_workstation_key_verified",
        table_name="wacom_execution_ceremony_challenges",
        entity_type="wacom_execution_ceremony_challenge", record_id=row.id,
        severity="high", status="success",
        description="Workstation Ed25519 key possession only; NO borrower signature",
        event_data={
            "workstation_id": str(row.workstation_id),
            "contract_id": str(row.contract_id),
            "candidate_sha256": row.candidate_sha256,
            "proof_message_sha256": row.workstation_proof_sha256,
            "physical_stu540_pen_verified": False,
            "borrower_affirmed": False,
            "contract_signed": False,
        },
    ))
    if datetime.now(timezone.utc) >= row.expires_at.replace(
        tzinfo=timezone.utc
    ) if row.expires_at.tzinfo is None else datetime.now(timezone.utc) >= row.expires_at:
        db.rollback()
        raise HTTPException(409, "Ceremony expired before workstation proof commit")
    db.commit()
    return {
        "challenge_id": str(row.id),
        "status": "pending",
        "workstation_key_verified": True,
        "physical_stu540_pen_verified": False,
        "borrower_affirmed": False,
        "contract_signed": False,
        "execution_performed": False,
    }
