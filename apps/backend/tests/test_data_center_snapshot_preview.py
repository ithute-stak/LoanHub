"""Read-only snapshot protocol must never pretend durable replay exists."""
from pathlib import Path
from types import SimpleNamespace as N

import pytest

from services.data_center_branch_projection import BranchGrant
from services.data_center_snapshot import (
    KINDS, MAX_RESOURCE_ROWS, SnapshotUnavailable,
    bucket_from_rows, require_snapshot_management,
)


def grant(role="company_owner", wide=True):
    return BranchGrant(company_id="c1", branch_id=None if wide else "b1",
                       role=role, company_wide=wide)


def test_preview_requires_company_management_for_all_six_resources():
    require_snapshot_management(grant("company_admin"))
    for role in ("branch_manager", "finance_officer", "loan_officer", "hr_manager"):
        with pytest.raises(PermissionError):
            require_snapshot_management(grant(role, False))


def test_bucket_rejects_duplicate_ids():
    items = [N(id="r1", company_id="c1"), N(id="r1", company_id="c1")]
    with pytest.raises(SnapshotUnavailable):
        bucket_from_rows(items, grant(), lambda row, g: {
            "id": row.id, "company_id": g.company_id,
        })


def test_bucket_preserves_safe_keys():
    bucket = bucket_from_rows([N(id="r1")], grant(), lambda row, g: {
        "id": row.id, "company_id": g.company_id,
    })
    assert bucket == {"ids": ["r1"], "byId": {"r1": {"id": "r1", "company_id": "c1"}}}


def test_snapshot_is_bounded_and_explicitly_not_ready():
    root = Path(__file__).resolve().parents[1]
    source = (root / "services" / "data_center_snapshot.py").read_text()
    route = (root / "routers" / "data_center_snapshot.py").read_text()
    assert KINDS == ("branches", "loanProducts", "staff", "clients", "loans", "payments")
    assert MAX_RESOURCE_ROWS == 500
    assert "REPEATABLE READ" in source
    assert ".limit(MAX_RESOURCE_ROWS + 1)" in source
    assert '"event_cursor": None' in source
    assert '"replay_supported": False' in source
    assert '"ready": False' in source
    assert '"complete_data_center_snapshot": False' in source
    assert 'status_code=409' in route
    assert '"private, no-store"' in route
