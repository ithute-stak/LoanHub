"""Internal Wacom candidate-evidence persistence. No HTTP endpoint or PDF signing.

Caller must independently establish workstation provenance and borrower
identity/consent. Ciphertext/object storage and database require recovery
reconciliation for failures spanning their transaction boundary.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models.origination import LoanContract
from database.models.pad_signing import ContractPadSigningSession, ContractPadCaptureEvidence
from services.pad_signature_evidence import validate_capture
from services.signature_evidence_vault import store_encrypted_signature_evidence


def persist_verified_candidate_capture(
    *, db: Session, storage, encryption_key_b64: str,
    company_id: UUID, borrower_id: UUID, contract_id: UUID, session_id: UUID,
    operator_id: UUID, strokes: list, capture_provenance_verified: bool,
    now: datetime | None = None,
) -> dict:
    """Persist one encrypted capture under database locks, never sign a loan.

    Provenance flag must come from a future independently authenticated
    connector, NEVER be exposed as a caller-controlled API parameter.
    """
    now = now or datetime.now(timezone.utc)
    if not capture_provenance_verified:
        raise HTTPException(403, "Authenticated Wacom provenance required")
    if now.tzinfo is None:
        raise HTTPException(409, "Timezone-aware signing time required")

    contract = (
        db.query(LoanContract)
        .filter(
            LoanContract.id == contract_id,
            LoanContract.company_id == company_id,
            LoanContract.borrower_id == borrower_id,
        )
        .with_for_update(of=LoanContract)
        .one_or_none()
    )
    if contract is None:
        raise HTTPException(404, "Loan contract not found")
    if (
        contract.pdf_file_id is None or contract.borrower_signed_at is not None
        or contract.locked_at is not None or contract.status == "signed"
    ):
        raise HTTPException(409, "Contract not eligible for pad capture")

    session = (
        db.query(ContractPadSigningSession)
        .filter(
            ContractPadSigningSession.id == session_id,
            ContractPadSigningSession.company_id == company_id,
            ContractPadSigningSession.contract_id == contract_id,
            ContractPadSigningSession.operator_user_id == operator_id,
        )
        .with_for_update(of=ContractPadSigningSession)
        .one_or_none()
    )
    if session is None:
        raise HTTPException(404, "Signing session not found")
    expiry = session.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if (
        session.status != "consented" or now >= expiry
        or not session.verified_identity_at or not session.consent_at
        or not session.consent_version or session.contract_hash != contract.contract_hash
        or session.evidence_sha256 is not None or session.evidence is not None
    ):
        raise HTTPException(409, "Fresh verified consented unused session required")

    validation = validate_capture(
        expected_contract_id=contract_id,
        contract_id=contract_id,
        contract_hash=contract.contract_hash,
        expected_contract_hash=contract.contract_hash,
        strokes=strokes, input_method="wacom_stu",
    )
    envelope = {
        "version": 1, "company_id": str(company_id),
        "borrower_id": str(borrower_id), "contract_id": str(contract_id),
        "contract_hash": contract.contract_hash, "session_id": str(session_id),
        "capture_source": "wacom_stu", "capture_digest": validation["sha256"],
        "strokes": strokes,
    }
    raw = json.dumps(envelope, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    object_key = None
    try:
        object_key, digest = store_encrypted_signature_evidence(
            storage, raw, key_b64=encryption_key_b64,
            company_id=company_id, borrower_id=borrower_id,
            session_id=session_id, contract_hash=contract.contract_hash,
        )
        db.add(ContractPadCaptureEvidence(
            company_id=company_id, session_id=session_id,
            encrypted_storage_key=object_key,
            evidence_sha256=digest, capture_source="wacom_stu",
        ))
        session.evidence_sha256 = digest
        session.status = "captured"
        db.commit()
    except Exception:
        db.rollback()
        if object_key is not None:
            try:
                storage.delete(object_key)
            except Exception:
                pass  # Orphan ciphertext requires periodic reconciliation.
        raise
    return {
        "session_id": str(session_id), "status": "captured",
        "evidence_sha256": digest, "capture_digest": validation["sha256"],
        "contract_signed": False,
    }
