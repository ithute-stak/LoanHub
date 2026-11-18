from types import SimpleNamespace

from routers.cdas_government_employees import assemble_discovery


def record(number, borrower, verified=False):
    return SimpleNamespace(employee_number=number, borrower_id=borrower, verified=verified)


def test_same_borrower_merges_sources_without_provider_call():
    rows = assemble_discovery([record(" EMP-001 ", "b1", True)], [record("emp-001", "b1")])
    assert len(rows) == 1
    assert rows[0]["status"] == "locally_verified"
    assert rows[0]["sources"] == ["employment", "payroll"]


def test_legacy_collision_never_selects_a_borrower():
    rows = assemble_discovery([record("EMP-001", "old", True)], [record("emp-001", "new")])
    assert rows[0]["borrower_id"] is None
    assert rows[0]["status"] == "identity_conflict"
    assert rows[0]["requires_manual_review"]


def test_missing_numbers_are_ignored():
    assert assemble_discovery([], [record("   ", "b1")]) == []


def test_unverified_source_is_not_assumed_government_employee():
    rows = assemble_discovery([], [record("ABC-99", "b1")])
    assert rows[0]["status"] == "requires_verification"
