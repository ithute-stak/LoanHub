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


from datetime import date
from routers.cdas_government_employees import compare_employee_identity


def identity():
    return SimpleNamespace(first_name="Mpho", last_name="Mokoena", date_of_birth=date(1990, 1, 1))


def provider(**changes):
    data = {"EmployeeNo": "EMP-100", "Name": "Mpho", "Surname": "Mokoena",
            "DOB": "1990-01-01", "TerminationDate": None}
    data.update(changes)
    return data


def test_matching_identity_can_be_preferred_for_human_review():
    assert compare_employee_identity(person=identity(), employee=provider(), expected_number="EMP-100") == []


def test_wrong_employee_number_is_rejected():
    errors = compare_employee_identity(person=identity(), employee=provider(EmployeeNo="EMP-999"), expected_number="EMP-100")
    assert "employee_number_mismatch" in errors


def test_name_and_dob_mismatch_fails_closed():
    errors = compare_employee_identity(person=identity(), employee=provider(Name="Other", DOB=None), expected_number="EMP-100")
    assert "given_name_mismatch_or_missing" in errors
    assert "date_of_birth_mismatch_or_missing" in errors


def test_termination_is_not_marked_as_eligible():
    errors = compare_employee_identity(person=identity(), employee=provider(TerminationDate="2026-10-01"), expected_number="EMP-100")
    assert "employment_terminated" in errors
