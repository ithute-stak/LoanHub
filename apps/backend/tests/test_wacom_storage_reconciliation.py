"""Read-only Wacom storage reconciliation: never automatically delete objects."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as R
from uuid import uuid4

import pytest
from services.wacom_storage_reconciliation import reconcile_wacom_candidates


def sample():
    now = datetime(2026, 11, 9, 9, tzinfo=timezone.utc)
    company, file_id, receipt_id = uuid4(), uuid4(), uuid4()
    candidate = R(
        id=file_id, company_id=company,
        category="wacom_execution_candidate",
        storage_key=f"{company}/artifact.bin", checksum_sha256="a"*64,
        created_at=now-timedelta(hours=3), is_deleted=False,
    )
    receipt = R(
        id=receipt_id, company_id=company,
        executed_file_id=file_id, executed_pdf_sha256="a"*64,
        status="reserved", executed_at=None,
    )
    return dict(
        company_id=company, managed_files=[candidate], receipts=[receipt],
        storage_keys=[candidate.storage_key], inventory_complete=True, now=now,
    )


def test_clean_snapshot():
    assert reconcile_wacom_candidates(**sample()) == []


def test_missing_blob_only_with_complete_inventory():
    v = sample()
    v["storage_keys"] = []
    assert "candidate_object_missing" in [
        f.code for f in reconcile_wacom_candidates(**v)
    ]
    v["inventory_complete"] = False
    codes = [f.code for f in reconcile_wacom_candidates(**v)]
    assert "candidate_object_missing" not in codes
    assert "storage_inventory_incomplete" in codes


def test_unattributed_object_never_assumed_wacom():
    v = sample()
    v["storage_keys"].append(f'{v["company_id"]}/unknown.bin')
    results = reconcile_wacom_candidates(**v)
    assert any(x.code == "unattributed_storage_object" for x in results)
    assert not any("safe_to_delete" in x.code for x in results)


def test_candidate_metadata_without_receipt_only_after_age_cutoff():
    v = sample()
    v["receipts"] = []
    assert "candidate_metadata_without_receipt" in [
        f.code for f in reconcile_wacom_candidates(**v)
    ]
    v["managed_files"][0].created_at = v["now"]
    assert "candidate_metadata_without_receipt" not in [
        f.code for f in reconcile_wacom_candidates(**v)
    ]


def test_receipt_metadata_and_digest_mismatch():
    v = sample()
    v["receipts"][0].executed_pdf_sha256 = "0"*64
    assert "receipt_candidate_digest_mismatch" in [
        f.code for f in reconcile_wacom_candidates(**v)
    ]


def test_rejects_cross_company_snapshot():
    v = sample()
    v["managed_files"][0].company_id = uuid4()
    with pytest.raises(ValueError, match="Cross-company"):
        reconcile_wacom_candidates(**v)


def test_detects_duplicate_keys():
    v = sample()
    v["storage_keys"].append(v["storage_keys"][0])
    with pytest.raises(ValueError):
        reconcile_wacom_candidates(**v)


def test_report_is_pure_and_does_not_mutate_storage():
    import inspect
    from services import wacom_storage_reconciliation as svc
    code = inspect.getsource(svc)
    for forbidden in ("db.commit(", ".delete(", "unlink(", "borrower_signed_at ="):
        assert forbidden not in code
