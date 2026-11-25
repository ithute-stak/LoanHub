"""Integrity certification for *managed* immutable CDAS consent evidence.

Never fetch arbitrary BorrowerDocument.file_url values, external URLs or paths.
The only acceptable evidence bytes are returned by LoanHub's managed storage
reader, which already decrypts and checks its persisted SHA-256 checksum.
This is a prerequisite to human consent review, not automatic approval.
"""
import hashlib
import hmac
import re
from uuid import UUID

from fastapi import HTTPException

from services.file_service import read_file_bytes

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_EVIDENCE_BYTES = 20 * 1024 * 1024
SUPPORTED_MIME = {"application/pdf", "image/png", "image/jpeg"}


def verify_managed_cdas_consent_bytes(
    *, file, company_id: UUID, borrower_id: UUID, expected_digest: str | None = None,
) -> str:
    if file is None or getattr(file, "company_id", None) != company_id:
        raise HTTPException(409, "Company-scoped consent file unavailable")
    if getattr(file, "is_deleted", True) or getattr(file, "quarantined_reason", None):
        raise HTTPException(409, "Consent file is deleted or quarantined")
    if getattr(file, "scan_status", None) != "clean":
        raise HTTPException(409, "Consent file has not passed clean malware scanning")
    if (
        getattr(file, "linked_entity_type", None) != "borrower_evaluation"
        or getattr(file, "linked_entity_id", None) != str(borrower_id)
    ):
        raise HTTPException(409, "Consent file is not linked to this borrower")
    if getattr(file, "mime_type", None) not in SUPPORTED_MIME:
        raise HTTPException(409, "Consent evidence must be a supported document image or PDF")
    size = getattr(file, "size_bytes", None)
    if not isinstance(size, int) or not 1 <= size <= MAX_EVIDENCE_BYTES:
        raise HTTPException(409, "Consent evidence file size is unavailable or too large")
    checksum = getattr(file, "checksum_sha256", None)
    if not isinstance(checksum, str) or _SHA256.fullmatch(checksum) is None:
        raise HTTPException(409, "Consent evidence stored checksum is invalid")
    # read_file_bytes fails closed if storage cannot decrypt/retrieve matching bytes.
    contents = read_file_bytes(file)
    if len(contents) != size:
        raise HTTPException(409, "Consent evidence byte count has changed")
    digest = hashlib.sha256(contents).hexdigest()
    if not hmac.compare_digest(checksum, digest):
        raise HTTPException(409, "Consent evidence checksum mismatch")
    if expected_digest is not None and (
        _SHA256.fullmatch(expected_digest) is None
        or not hmac.compare_digest(expected_digest, digest)
    ):
        raise HTTPException(409, "Consent evidence content differs from reviewer-approved bytes")
    if (file.mime_type == "application/pdf" and not contents.startswith(b"%PDF-")) or (
        file.mime_type == "image/png" and not contents.startswith(b"\x89PNG\r\n\x1a\n")
    ) or (file.mime_type == "image/jpeg" and not contents.startswith(b"\xff\xd8\xff")):
        raise HTTPException(409, "Consent evidence content does not match its document type")
    return digest
