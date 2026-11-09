"""Read-only verification of archived Wacom candidate plaintext hashes.

The caller must supply an authorized tenant-scoped, bounded database snapshot.
No bytes are returned in findings, and no storage, DB or contract mutation occurs.
Storage decryption/transport errors are reported as unverifiable, not healed.
"""
from __future__ import annotations

import hashlib
import hmac

from services.wacom_storage_reconciliation import Finding


def verify_candidate_contents(
    *, company_id, managed_files, receipts, read_bytes, max_records=10000,
):
    """Check stored PDF candidate ciphertext via the existing verified reader.

    read_bytes is the same verified managed-file reader used by LoanHub.
    A matching ManagedFile checksum is insufficient if the receipt's digest differs.
    """
    files, rows = list(managed_files), list(receipts)
    if not 1 <= max_records <= 10000 or len(files) > max_records or len(rows) > max_records:
        raise ValueError("Unbounded verification snapshot")
    if any(f.company_id != company_id for f in files) or any(
        r.company_id != company_id for r in rows
    ):
        raise ValueError("Cross-company candidate audit input")
    candidates = {}
    for f in files:
        if f.id in candidates:
            raise ValueError("Duplicate managed file ID")
        candidates[f.id] = f
    findings = []
    seen = set()
    for receipt in rows:
        f = candidates.get(receipt.executed_file_id)
        if f is None or f.category != "wacom_execution_candidate":
            findings.append(Finding(
                "candidate_metadata_not_available_for_byte_verification",
                file_id=str(receipt.executed_file_id) if receipt.executed_file_id else None,
                receipt_id=str(receipt.id),
            ))
            continue
        if f.id in seen:
            continue
        seen.add(f.id)
        if (f.is_deleted or not f.is_encrypted or not f.is_confidential
                or f.scan_status != "clean" or f.mime_type != "application/pdf"):
            findings.append(Finding(
                "candidate_file_security_metadata_invalid",
                file_id=str(f.id), receipt_id=str(receipt.id),
            ))
            continue
        try:
            data = read_bytes(f)
        except Exception:
            # Never report plaintext or underlying storage paths/error text.
            findings.append(Finding(
                "candidate_contents_unavailable",
                file_id=str(f.id), receipt_id=str(receipt.id),
            ))
            continue
        if not isinstance(data, bytes) or not data.startswith(b"%PDF-"):
            findings.append(Finding(
                "candidate_contents_not_pdf",
                file_id=str(f.id), receipt_id=str(receipt.id),
            ))
            continue
        digest = hashlib.sha256(data).hexdigest()
        expected = (f.checksum_sha256, receipt.executed_pdf_sha256)
        if any(
            not isinstance(value, str) or len(value) != 64
            or not hmac.compare_digest(digest, value)
            for value in expected
        ):
            findings.append(Finding(
                "candidate_contents_hash_mismatch",
                file_id=str(f.id), receipt_id=str(receipt.id),
            ))
    return sorted(findings, key=lambda f: (f.code, f.receipt_id or ""))
