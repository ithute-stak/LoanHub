"""Simulated S3 pagination/failure cases: never infer completeness after failure."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from scripts.wacom_reconcile_storage import inventory_for_company


class FakeS3:
    provider = "s3"
    bucket = "synthetic-bucket"
    prefix = "loanhub-tests"

    def __init__(self, pages):
        self.pages = pages
        self.calls = []
        self.client = self

    def _key(self, value):
        return self.prefix + "/" + value

    def list_objects_v2(self, **kwargs):
        self.calls.append(kwargs)
        page = len(self.calls) - 1
        response = self.pages[page]
        if isinstance(response, Exception):
            raise response
        return response


def test_complete_paginated_s3_tenant_inventory():
    company = uuid4()
    provider = FakeS3([
        {
            "IsTruncated": True,
            "NextContinuationToken": "synthetic-page-2",
            "Contents": [{"Key": f"loanhub-tests/{company}/a.bin"}],
        },
        {
            "IsTruncated": False,
            "Contents": [{"Key": f"loanhub-tests/{company}/b.bin"}],
        },
    ])
    keys, complete = inventory_for_company(storage=provider, company_id=company)
    assert complete is True
    assert keys == [f"{company}/a.bin", f"{company}/b.bin"]
    assert provider.calls[1]["ContinuationToken"] == "synthetic-page-2"


def test_s3_missing_continuation_never_certifies_complete():
    company = uuid4()
    provider = FakeS3([{
        "IsTruncated": True,
        "Contents": [{"Key": f"loanhub-tests/{company}/a.bin"}],
    }])
    keys, complete = inventory_for_company(storage=provider, company_id=company)
    assert complete is False
    assert keys == [f"{company}/a.bin"]


def test_s3_pagination_error_fails_closed():
    company = uuid4()
    provider = FakeS3([
        {
            "IsTruncated": True, "NextContinuationToken": "page-two",
            "Contents": [{"Key": f"loanhub-tests/{company}/a.bin"}],
        },
        OSError("synthetic S3 interruption"),
    ])
    with pytest.raises(OSError, match="interruption"):
        inventory_for_company(storage=provider, company_id=company)


def test_s3_foreign_tenant_object_is_rejected():
    company = uuid4()
    foreign = uuid4()
    provider = FakeS3([{
        "IsTruncated": False,
        "Contents": [{"Key": f"loanhub-tests/{foreign}/foreign.bin"}],
    }])
    with pytest.raises(ValueError, match="outside tenant prefix"):
        inventory_for_company(storage=provider, company_id=company)


def test_s3_pagination_limit_does_not_report_complete():
    company = uuid4()
    provider = FakeS3([{
        "IsTruncated": False,
        "Contents": [
            {"Key": f"loanhub-tests/{company}/first.bin"},
            {"Key": f"loanhub-tests/{company}/second.bin"},
        ],
    }])
    keys, complete = inventory_for_company(
        storage=provider, company_id=company, max_records=1,
    )
    assert complete is False
    assert len(keys) == 1
