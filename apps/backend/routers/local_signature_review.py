"""Independent review of locally captured Wacom handwriting evidence.

Verification attests only that a human reviewer checked identity, consent
and the capture file. It does NOT create BorrowerSavedSignature, authorize
reuse, attach handwriting to a contract, or sign a document.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES, TenantContext, get_tenant_context,
    require_tenant_roles,
)
from database.models.audit_log import AuditLog
from database.models.file_management import ManagedFile
from database.session import get_db

router = APIRouter(prefix="/local-signatures/review", tags=["Local Wacom Evidence Review"])

PENDING = {"wacom_operator_signature_pending", "wacom_client_signature_pending"}
VERIFIED = {
    "wacom_operator_signature_pending": "wacom_operator_capture_verified",
    "wacom_client_signature_pending": "wacom_client_capture_verified",
}
REJECTED = {
    "wacom_operator_signature_pending": "wacom_operator_capture_rejected",
    "wacom_client_signature_pending": "wacom_client_capture_rejected",
}


class EvidenceDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern="^(verify|reject)$")
    identity_checked: bool = False
    consent_checked: bool = False
    evidence_reference: str = Field(min_length=4, max_length=160)
    reason: str = Field(min_length=8, max_length=400)


def _reviewer(context: TenantContext) -> None:
    if context.company_id is None or context.staff is None:
        raise HTTPException(403, "Active company management membership required")
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)


def _capture_meta(record: ManagedFile) -> dict:
    return {
        "capture_file_id": str(record.id),
        "captured_by_user_id": str(record.owner_user_id) if record.owner_user_id else None,
        "company_id": str(record.company_id),
        "branch_id": str(record.branch_id) if record.branch_id else None,
        "signer_kind": "operator" if "operator" in record.category else "client",
        "signer_id": record.linked_entity_id,
        "evidence_status": "verified" if record.category in VERIFIED.values()
            else "rejected" if record.category in REJECTED.values() else "pending_review",
        "captured_at": record.created_at,
        "scan_status": record.scan_status,
        "usable_for_signing": False,
        "automatic_reuse_allowed": False,
    }


@router.get("")
def pending_evidence(
    response: Response,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    _reviewer(context)
    records = (
        db.query(ManagedFile)
        .filter(
            ManagedFile.company_id == context.company_id,
            ManagedFile.category.in_(PENDING),
            ManagedFile.is_deleted.is_(False),
            ManagedFile.is_confidential.is_(True),
            ManagedFile.visibility == "private",
        )
        .order_by(ManagedFile.created_at.asc(), ManagedFile.id.asc())
        .limit(limit)
        .all()
    )
    # Metadata only. File content access is still separately protected.
    return {"captures": [_capture_meta(item) for item in records]}


@router.post("/{file_id}/decision")
def review_capture(
    file_id: UUID,
    payload: EvidenceDecision,
    response: Response,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    _reviewer(context)
    record = (
        db.query(ManagedFile)
        .filter(
            ManagedFile.id == file_id,
            ManagedFile.company_id == context.company_id,
            ManagedFile.category.in_(PENDING),
            ManagedFile.is_deleted.is_(False),
            ManagedFile.is_confidential.is_(True),
            ManagedFile.visibility == "private",
        )
        .with_for_update()
        .one_or_none()
    )
    if record is None:
        raise HTTPException(404, "Pending capture unavailable")
    if record.owner_user_id is None or record.owner_user_id == context.user.id:
        raise HTTPException(403, "Independent reviewer required")
    if not record.is_encrypted:
        raise HTTPException(409, "Capture is not encrypted")
    if record.scan_status != "clean":
        raise HTTPException(409, "Capture has no clean malware scan")
    if not record.linked_entity_id or record.linked_entity_type not in {
        "wacom_client", "wacom_operator",
    }:
        raise HTTPException(409, "Capture signer identity is incomplete")
    if ("operator" in record.category) != (record.linked_entity_type == "wacom_operator"):
        raise HTTPException(409, "Capture signer identity is inconsistent")
    if payload.decision == "verify" and (not payload.identity_checked or not payload.consent_checked):
        raise HTTPException(422, "Identity and consent checks are required for verification")

    old_category = record.category
    record.category = (
        VERIFIED[old_category] if payload.decision == "verify"
        else REJECTED[old_category]
    )
    db.add(AuditLog(
        user_id=context.user.id,
        company_id=context.company_id,
        branch_id=context.branch_id,
        action="local_signatures.capture_reviewed",
        table_name="managed_files",
        entity_type="wacom_signature_capture",
        record_id=record.id,
        actor_role=context.role.value,
        severity="high",
        description="Independent review of Wacom handwriting evidence; not a signing authorization",
        before_data={"category": old_category},
        after_data={"category": record.category},
        changed_fields=["category"],
        event_data={
            "decision": payload.decision,
            "evidence_reference": payload.evidence_reference,
            "identity_checked": payload.identity_checked,
            "consent_checked": payload.consent_checked,
            "review_reason": payload.reason,
            "source_sha256": record.checksum_sha256,
            "submitted_by_user_id": str(record.owner_user_id),
            "signer_kind": record.linked_entity_type,
            "signer_id": record.linked_entity_id,
            "authorizes_signing": False,
        },
    ))
    db.commit()
    return _capture_meta(record)
