"""Regression tests for employer cleanup planning; no database required."""
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from scripts.normalize_legacy_employers import plan


def record(company, name, **kwargs):
    return SimpleNamespace(
        id=uuid4(), company_id=company,
        name=name, employer=name,
        normalized_name=name.casefold(),
        created_at=datetime(2026, 1, 1),
        **kwargs,
    )


def test_case_insensitive_dedup_preserves_deductions_and_company_boundaries():
    one, two = uuid4(), uuid4()
    keeper = record(one, "Tsepong")
    duplicate = record(one, "TSEPONG")
    other_company = record(two, "TSEPONG")
    first = record(one, "tsepong")
    second = record(one, " TSEPONG ")
    changes = plan([keeper, duplicate, other_company], [first, second])
    assert ("delete_directory_duplicate", str(one), str(duplicate.id)) in changes
    assert ("rename_deduction", str(one), str(first.id), "Tsepong") in changes
    assert ("rename_deduction", str(one), str(second.id), "Tsepong") in changes
    assert all(change[2] != str(other_company.id) for change in changes)


def test_existing_unregistered_employer_is_not_dropped():
    company = uuid4()
    first, second = record(company, "Motheo"), record(company, "MOTHEO")
    changes = plan([], [first, second])
    assert len([x for x in changes if x[0] == "rename_deduction"]) == 1
    assert not any(x[0] == "delete_directory_duplicate" for x in changes)
