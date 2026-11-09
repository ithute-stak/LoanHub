"""Read-only independent integrity verification of archived Wacom PDF candidates.

A green result attests to the stored artifact's hashes and authorization chain,
not to legal execution, borrower signature validity, or a cryptographic PDF
signature. Never changes contract state or authorization status.
"""
from __future__ import annotations

import hashlib
import io
from datetime import datetime, timezone

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from services.wacom_approved_field import stored_field_matches


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _digest(content, expected):
    return (isinstance(content, bytes) and isinstance(expected, str)
            and len(expected) == 64
            and hashlib.sha256(content).hexdigest() == expected)


def candidate_archive_blockers(
    *, receipt, intent, approval, packet, authorization, contract,
    source_file, evidence_file, packet_file, candidate_file,
    source_pdf, handwriting_png, packet_pdf, candidate_pdf,
):
    """Return independently auditable denial codes, never an execution grant."""
    if any(v is None for v in (
        receipt, intent, approval, packet, authorization, contract,
        source_file, evidence_file, packet_file, candidate_file,
    )):
        return ["archive_chain_missing"]
    errors = []
    company = intent.company_id
    if any(getattr(item, "company_id", None) != company for item in (
        receipt, approval, packet, authorization, contract,
        source_file, evidence_file, packet_file, candidate_file,
    )):
        errors.append("cross_tenant_archive")
    if (receipt.intent_id != intent.id or receipt.contract_id != intent.contract_id
            or receipt.authorization_id != authorization.id
            or receipt.packet_id != packet.id
            or approval.intent_id != intent.id or packet.intent_id != intent.id
            or authorization.intent_id != intent.id
            or packet.approval_id != approval.id):
        errors.append("archive_reference_chain_changed")
    if (contract.id != intent.contract_id or contract.borrower_id != intent.borrower_id
            or intent.source_file_id != source_file.id
            or intent.evidence_file_id != evidence_file.id
            or receipt.executed_file_id != candidate_file.id
            or packet.packet_file_id != packet_file.id):
        errors.append("archive_file_identity_changed")
    if (receipt.status != "reserved" or receipt.executed_at is not None
            or getattr(receipt, "field_binding_sha256", None)
            != getattr(authorization, "field_binding_sha256", None)):
        errors.append("candidate_receipt_state_changed")

    if (authorization.status != "approved" or authorization.consumed_at is not None
            or authorization.authorized_by is None):
        errors.append("execution_permit_state_changed")
    approved_at = _utc(getattr(authorization, "authorized_at", None))
    reserved_at = _utc(getattr(receipt, "reserved_at", None))
    expires_at = _utc(getattr(authorization, "expires_at", None))
    if (approved_at is None or reserved_at is None or expires_at is None
            or not approved_at <= reserved_at < expires_at):
        errors.append("archive_outside_authorized_window")
    if (approval.status != "consumed" or approval.consumed_at is None
            or approval.decided_by is None or not approval.decision_reference
            or packet.archived_at is None):
        errors.append("evidence_archive_not_approved")
    if (intent.status != "verified" or not intent.consent_reference
            or not intent.consent_commitment_sha256
            or not intent.review_reference or intent.review_by is None):
        errors.append("consent_or_evidence_missing")
    if any(
        getattr(receipt, attr, None) != getattr(intent, attr, None)
        or getattr(authorization, attr, None) != getattr(intent, attr, None)
        or getattr(approval, attr, None) != getattr(intent, attr, None)
        for attr in ("document_sha256", "evidence_sha256", "binding_sha256")
    ):
        errors.append("source_evidence_binding_changed")
    if (packet.source_sha256 != intent.document_sha256
            or packet.handwriting_sha256 != intent.evidence_sha256):
        errors.append("archived_packet_binding_changed")

    for obj, digest, data in (
        (source_file, intent.document_sha256, source_pdf),
        (evidence_file, intent.evidence_sha256, handwriting_png),
        (packet_file, packet.packet_sha256, packet_pdf),
        (candidate_file, receipt.executed_pdf_sha256, candidate_pdf),
    ):
        if (obj.is_deleted or not obj.is_encrypted or obj.scan_status != "clean"
                or obj.checksum_sha256 != digest or not _digest(data, digest)):
            errors.append("archived_file_integrity_failure")
            break
    if (not candidate_file.is_confidential
            or candidate_file.category != "wacom_execution_candidate"
            or candidate_file.mime_type != "application/pdf"
            or candidate_file.id in {source_file.id, packet_file.id}):
        errors.append("candidate_storage_classification_changed")
    if not stored_field_matches(
        authorization=authorization,
        source_pdf=source_pdf,
        expected_sha256=intent.document_sha256,
    ):
        errors.append("approved_field_binding_changed")
    if isinstance(candidate_pdf, bytes) and candidate_pdf == source_pdf:
        errors.append("candidate_does_not_change_original")
    if (not isinstance(candidate_pdf, bytes)
            or len(candidate_pdf) > 25 * 1024 * 1024
            or not candidate_pdf.startswith(b"%PDF-")):
        errors.append("candidate_pdf_malformed")
    else:
        try:
            parsed = PdfReader(io.BytesIO(candidate_pdf), strict=True)
            if (parsed.is_encrypted or len(parsed.pages) != authorization.field_page_count
                    or any(int(page.get("/Rotate", 0)) % 360 for page in parsed.pages)):
                errors.append("candidate_pdf_structure_changed")
        except (ValueError, TypeError, KeyError, OSError, PdfReadError):
            errors.append("candidate_pdf_malformed")
    return errors
