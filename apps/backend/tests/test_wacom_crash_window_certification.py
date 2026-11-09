"""Synthetic crash-window certification for Wacom archive recovery.

No production objects, borrower records or signing operations are touched.
Simulates storage and database snapshots at interrupted write/commit boundaries.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from types import SimpleNamespace as Row
from uuid import uuid4

from services.object_storage_service import LocalObjectStorage
from services.wacom_storage_reconciliation import reconcile_wacom_candidates
from scripts.wacom_reconcile_storage import inventory_for_company


def context(tmp_path):
    company = uuid4()
    store = LocalObjectStorage(str(tmp_path))
    now = datetime.now(timezone.utc)
    pdf = b"%PDF-1.4\nSynthetic recovery candidate\n%%EOF"
    digest = sha256(pdf).hexdigest()
    key = f"{company}/{uuid4()}.bin"
    file = Row(
        id=uuid4(), company_id=company,
        category="wacom_execution_candidate",
        storage_key=key, checksum_sha256=digest, is_deleted=False,
        created_at=now - timedelta(hours=2),
    )
    receipt = Row(
        id=uuid4(), company_id=company, executed_file_id=file.id,
        executed_pdf_sha256=digest, status="reserved", executed_at=None,
    )
    return Row(
        company=company, storage=store, now=now, content=pdf,
        key=key, file=file, receipt=receipt,
    )


def inspect(ctx, *, files, receipts, max_records=10000):
    keys, complete = inventory_for_company(
        storage=ctx.storage, company_id=ctx.company, max_records=max_records,
    )
    return reconcile_wacom_candidates(
        company_id=ctx.company, managed_files=files, receipts=receipts,
        storage_keys=keys, inventory_complete=complete, now=ctx.now,
    )


def codes(items):
    return {f.code for f in items}


def test_prewrite_crash_has_no_persisted_evidence(tmp_path):
    ctx = context(tmp_path)
    assert inspect(ctx, files=[], receipts=[]) == []


def test_crash_after_object_write_before_database_insert(tmp_path):
    ctx = context(tmp_path)
    ctx.storage.put(ctx.key, ctx.content)
    findings = inspect(ctx, files=[], receipts=[])
    assert codes(findings) == {"unattributed_storage_object"}
    # The reconciliation checker MUST NOT remove an untracked object.
    assert ctx.storage.get(ctx.key) == ctx.content


def test_crash_after_managed_file_before_receipt(tmp_path):
    ctx = context(tmp_path)
    ctx.storage.put(ctx.key, ctx.content)
    result = inspect(ctx, files=[ctx.file], receipts=[])
    assert "candidate_metadata_without_receipt" in codes(result)
    assert ctx.storage.get(ctx.key) == ctx.content


def test_database_committed_but_storage_missing(tmp_path):
    ctx = context(tmp_path)
    result = inspect(ctx, files=[ctx.file], receipts=[ctx.receipt])
    assert "candidate_object_missing" in codes(result)


def test_successful_commit_is_idempotent_under_repeated_audit(tmp_path):
    ctx = context(tmp_path)
    ctx.storage.put(ctx.key, ctx.content)
    a = inspect(ctx, files=[ctx.file], receipts=[ctx.receipt])
    b = inspect(ctx, files=[ctx.file], receipts=[ctx.receipt])
    assert a == b == []
    assert ctx.storage.get(ctx.key) == ctx.content


def test_rollback_cleanup_does_not_hide_other_tenant_objects(tmp_path):
    ctx = context(tmp_path)
    other = uuid4()
    ctx.storage.put(ctx.key, ctx.content)
    ctx.storage.put(f"{other}/evidence.bin", b"unrelated")
    findings = inspect(ctx, files=[], receipts=[])
    assert codes(findings) == {"unattributed_storage_object"}
    assert len(findings) == 1
    assert ctx.storage.get(f"{other}/evidence.bin") == b"unrelated"


def test_recent_inflight_candidate_is_not_flagged_stale(tmp_path):
    ctx = context(tmp_path)
    ctx.storage.put(ctx.key, ctx.content)
    ctx.file.created_at = ctx.now
    assert "candidate_metadata_without_receipt" not in codes(
        inspect(ctx, files=[ctx.file], receipts=[]),
    )


def test_snapshot_truncation_never_claims_missing_object(tmp_path):
    ctx = context(tmp_path)
    ctx.storage.put(ctx.key, ctx.content)
    ctx.storage.put(f"{ctx.company}/second.bin", b"second")
    keys, complete = inventory_for_company(
        storage=ctx.storage, company_id=ctx.company, max_records=1,
    )
    assert complete is False
    result = reconcile_wacom_candidates(
        company_id=ctx.company, managed_files=[ctx.file],
        receipts=[ctx.receipt], storage_keys=keys,
        inventory_complete=complete, now=ctx.now,
    )
    assert "storage_inventory_incomplete" in codes(result)
    assert "candidate_object_missing" not in codes(result)


def test_reconciliation_does_not_mutate_local_storage(tmp_path):
    ctx = context(tmp_path)
    ctx.storage.put(ctx.key, ctx.content)
    original = ctx.storage.get(ctx.key)
    inspect(ctx, files=[], receipts=[])
    assert ctx.storage.get(ctx.key) == original
