"""Read-only Wacom archive crash-recovery classification.

A PostgreSQL transaction cannot atomically commit an object-storage write.
This module provides deterministic reconciliation findings, NEVER deletes,
retries, relabels, or marks a contract signed. An unreferenced object may be
unrelated to Wacom and is NOT automatically safe to delete.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable


@dataclass(frozen=True)
class Finding:
    code: str
    key: str | None = None
    receipt_id: str | None = None
    file_id: str | None = None


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def reconcile_wacom_candidates(
    *, company_id, managed_files: Iterable, receipts: Iterable,
    storage_keys: Iterable[str], inventory_complete: bool,
    now: datetime | None = None, min_age_minutes: int = 60,
    max_records: int = 10000,
) -> list[Finding]:
    """Compare bounded, tenant-scoped snapshots; report only, no side effects.

    storage_keys must represent a COMPLETE snapshot of a single tenant's
    storage prefix. If incomplete, absence is *not* evidence of a missing file.
    """
    now = _utc(now or datetime.now(timezone.utc))
    if now is None or not 1 <= min_age_minutes <= 10080 or not 1 <= max_records <= 100000:
        raise ValueError("Invalid reconciliation parameters")
    files, rows, keys = list(managed_files), list(receipts), list(storage_keys)
    if any(len(part) > max_records for part in (files, rows, keys)):
        raise ValueError("Reconciliation snapshot too large")
    if len(keys) != len(set(keys)):
        raise ValueError("Storage snapshot contains duplicate keys")
    if any(not isinstance(k, str) or not k.strip() for k in keys):
        raise ValueError("Invalid storage key")

    cutoff = now - timedelta(minutes=min_age_minutes)
    findings: list[Finding] = []
    by_file_id = {}
    referenced_keys = set()
    candidates = {}
    for item in files:
        if item.company_id != company_id:
            raise ValueError("Cross-company managed file in reconciliation input")
        if item.id in by_file_id:
            raise ValueError("Duplicate managed file ID")
        by_file_id[item.id] = item
        if not isinstance(item.storage_key, str) or not item.storage_key:
            raise ValueError("Managed file storage key missing")
        referenced_keys.add(item.storage_key)
        if item.category == "wacom_execution_candidate":
            candidates[item.id] = item
            if (inventory_complete and item.storage_key not in keys
                    and not item.is_deleted):
                findings.append(Finding(
                    "candidate_object_missing", item.storage_key, file_id=str(item.id),
                ))
    receipt_refs = set()
    seen_receipts = set()
    for receipt in rows:
        if receipt.company_id != company_id:
            raise ValueError("Cross-company receipt in reconciliation input")
        if receipt.id in seen_receipts:
            raise ValueError("Duplicate receipt ID")
        seen_receipts.add(receipt.id)
        if receipt.executed_file_id is None:
            findings.append(Finding("receipt_without_candidate", receipt_id=str(receipt.id)))
            continue
        if receipt.executed_file_id in receipt_refs:
            findings.append(Finding("candidate_referenced_by_multiple_receipts",
                                    receipt_id=str(receipt.id),
                                    file_id=str(receipt.executed_file_id)))
        receipt_refs.add(receipt.executed_file_id)
        candidate = candidates.get(receipt.executed_file_id)
        if candidate is None:
            findings.append(Finding("receipt_candidate_metadata_missing",
                                    receipt_id=str(receipt.id),
                                    file_id=str(receipt.executed_file_id)))
        elif candidate.checksum_sha256 != receipt.executed_pdf_sha256:
            findings.append(Finding("receipt_candidate_digest_mismatch",
                                    receipt_id=str(receipt.id),
                                    file_id=str(candidate.id)))
        if receipt.status != "reserved" or receipt.executed_at is not None:
            findings.append(Finding("candidate_record_wrong_execution_state",
                                    receipt_id=str(receipt.id)))
    for candidate in candidates.values():
        if candidate.id in receipt_refs or candidate.is_deleted:
            continue
        # A recent unreferenced file can be from an in-flight transaction.
        created = _utc(getattr(candidate, "created_at", None))
        if created is None:
            findings.append(Finding("candidate_age_unknown",
                                    candidate.storage_key, file_id=str(candidate.id)))
        elif created <= cutoff:
            findings.append(Finding("candidate_metadata_without_receipt",
                                    candidate.storage_key, file_id=str(candidate.id)))
    if inventory_complete:
        for key in keys:
            if key not in referenced_keys:
                # Unattributed: a missing ManagedFile row has no Wacom category.
                # Never delete on this signal; manually correlate backup logs.
                findings.append(Finding("unattributed_storage_object", key=key))
    else:
        findings.append(Finding("storage_inventory_incomplete"))
    return sorted(findings, key=lambda f: (f.code, f.key or "", f.receipt_id or ""))
