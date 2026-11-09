"""Storage inventory must remain bounded, tenant-scoped and read-only."""
from pathlib import Path
from types import SimpleNamespace as R
from uuid import uuid4

from scripts.wacom_reconcile_storage import inventory_for_company


class Local:
    provider = "local"
    def __init__(self, root):
        self.root = root
    def _path(self, key):
        return self.root / key


def test_local_inventory_returns_exact_company_only(tmp_path):
    company, other = uuid4(), uuid4()
    (tmp_path / str(company)).mkdir()
    (tmp_path / str(other)).mkdir()
    (tmp_path / str(company) / "one.bin").write_bytes(b"a")
    (tmp_path / str(other) / "hidden.bin").write_bytes(b"b")
    keys, complete = inventory_for_company(
        storage=Local(tmp_path), company_id=company)
    assert complete is True
    assert keys == [f"{company}/one.bin"]


def test_local_inventory_partial_if_truncated(tmp_path):
    company = uuid4()
    root = tmp_path / str(company)
    root.mkdir()
    for index in range(3):
        (root / f"{index}.bin").write_bytes(b"x")
    keys, complete = inventory_for_company(
        storage=Local(tmp_path), company_id=company, max_records=2)
    assert complete is False
    assert len(keys) == 2


class S3:
    provider = "s3"
    prefix = "wacom"
    bucket = "synthetic"
    def __init__(self, company):
        self.company = company
        self.queries = []
        self.client = self
    def _key(self, value):
        return "wacom/" + value
    def list_objects_v2(self, **kwargs):
        self.queries.append(kwargs)
        return {"IsTruncated": False, "Contents": [
            {"Key": f"wacom/{self.company}/one.bin"},
        ]}


def test_s3_inventory_uses_trailing_slash_prefix():
    company = uuid4()
    storage = S3(company)
    keys, complete = inventory_for_company(storage=storage, company_id=company)
    assert complete is True
    assert keys == [f"{company}/one.bin"]
    assert storage.queries[0]["Prefix"] == f"wacom/{company}/"


def test_inventory_has_no_delete_method_calls():
    import inspect
    from scripts import wacom_reconcile_storage
    source = inspect.getsource(wacom_reconcile_storage)
    assert ".delete(" not in source
    assert "db.commit(" not in source
