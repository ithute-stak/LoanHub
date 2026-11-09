"""Pure policy for a FUTURE database-locked PDF execution transaction.

A successful result is only eligible for reservation; it never signs a PDF.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from services.wacom_execution_preflight import execution_preflight_blockers


def reserve_execution_blockers(
    *, intent, approval, packet, execution_authorization, contract,
    source, evidence, executing_user_id, source_pdf, handwriting_png,
    existing_receipt=None, now=None,
):
    now = now or datetime.now(timezone.utc)
    reasons = execution_preflight_blockers(
        intent=intent, approval=approval, packet=packet,
        execution_authorization=execution_authorization,
        executing_user_id=executing_user_id, source_pdf=source_pdf,
        handwriting_png=handwriting_png, now=now,
    )
    if existing_receipt is not None:
        reasons.append("contract_already_reserved")
    if (execution_authorization is not None and packet is not None
            and getattr(execution_authorization, "packet_id", None) != getattr(packet, "id", None)):
        reasons.append("execution_packet_mismatch")
    if (execution_authorization is not None
            and getattr(execution_authorization, "authorized_at", None) is None):
        reasons.append("execution_decision_missing")
    if contract is None or intent is None:
        reasons.append("contract_unavailable")
    else:
        if (contract.company_id != intent.company_id
                or contract.id != intent.contract_id
                or contract.borrower_id != intent.borrower_id
                or contract.pdf_file_id != intent.source_file_id
                or str(contract.version) != intent.document_version):
            reasons.append("contract_identity_changed")
        if (contract.borrower_signed_at is not None
                or contract.locked_at is not None
                or contract.status == "signed"):
            reasons.append("contract_already_signed")
    if source is None or intent is None:
        reasons.append("source_unavailable")
    elif (source.id != intent.source_file_id
            or source.company_id != intent.company_id
            or source.checksum_sha256 != intent.document_sha256
            or source.mime_type != "application/pdf"
            or not source.is_encrypted or source.is_deleted
            or source.scan_status != "clean"):
        reasons.append("source_unavailable")
    if evidence is None or intent is None:
        reasons.append("evidence_unavailable")
    elif (evidence.id != intent.evidence_file_id
            or evidence.company_id != intent.company_id
            or evidence.checksum_sha256 != intent.evidence_sha256
            or evidence.category != "wacom_client_capture_verified"
            or evidence.linked_entity_id != str(intent.borrower_id)
            or evidence.linked_entity_type != "wacom_client"
            or not evidence.is_encrypted or not evidence.is_confidential
            or evidence.is_deleted or evidence.scan_status != "clean"):
        reasons.append("evidence_unavailable")
    if (intent is not None and source is not None
            and isinstance(source_pdf, bytes)
            and source.checksum_sha256 != hashlib.sha256(source_pdf).hexdigest()):
        reasons.append("source_file_bytes_changed")
    if (intent is not None and evidence is not None
            and isinstance(handwriting_png, bytes)
            and evidence.checksum_sha256 != hashlib.sha256(handwriting_png).hexdigest()):
        reasons.append("evidence_file_bytes_changed")
    return reasons
