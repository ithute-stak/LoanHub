from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import UniqueConstraint

from database.models.cdas_official import CdasDailyIntelligenceRun
from services.cdas_daily_run import serialize_daily_intelligence_run
from services.cdas_deduction_lifecycle import CdasLifecycleError
from services.cdas_exact_identity import (
    CdasExactIdentityError,
    require_exact_verified_payroll_profile,
)
from services.cdas_registration_workflow import _validate_fresh_exact_identity


_EXACT_NOTE = (
    "Exact-ID link basis: EXACT_LOANHUB_NATIONAL_ID_PLUS_CDAS_EMPLOYEE_NO. "
    "LoanHub client was resolved by exact normalized National ID; CDAS returned the exact requested EmployeeNo. "
    "CDAS v1.5 does not document a National ID in Employee Details, so no provider National ID claim was made. "
    "No fuzzy name or date-of-birth matching was used."
)


def test_daily_run_model_has_company_date_uniqueness_gate():
    unique_names = {
        constraint.name
        for constraint in CdasDailyIntelligenceRun.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert "uq_cdas_daily_intelligence_company_date" in unique_names


def test_daily_run_health_is_safe_before_first_run():
    payload = serialize_daily_intelligence_run(None, timezone_name="Africa/Maseru")
    assert payload["status"] == "not_run"
    assert payload["health"] == "awaiting_first_run"
    assert payload["provider_writes"] == 0
    assert payload["healthy"] is True


def test_completed_daily_run_exposes_read_only_health_counts():
    run = SimpleNamespace(
        scheduled_time="03:45",
        timezone="Africa/Maseru",
        status="completed",
        run_date=date(2026, 9, 23),
        started_at=datetime(2026, 9, 23, 1, 45),
        completed_at=datetime(2026, 9, 23, 1, 47),
        eligible_profiles=5,
        checked_profiles=5,
        ready_profiles=2,
        no_capacity_profiles=3,
        issue_count=0,
        provider_writes=0,
        error_message=None,
    )
    payload = serialize_daily_intelligence_run(run, timezone_name="Africa/Maseru")
    assert payload["health"] == "healthy"
    assert payload["checked_profiles"] == 5
    assert payload["ready_profiles"] == 2
    assert payload["provider_writes"] == 0


def test_exact_id_verified_profile_is_required_for_new_provider_write():
    exact = SimpleNamespace(
        verified=True,
        employee_number="0019336",
        verification_notes=_EXACT_NOTE,
    )
    assert require_exact_verified_payroll_profile(exact, requested_employee_no="0019336") is exact

    legacy = SimpleNamespace(
        verified=True,
        employee_number="0019336",
        verification_notes="Employee number, name, surname and date of birth matched.",
    )
    with pytest.raises(CdasExactIdentityError) as raised:
        require_exact_verified_payroll_profile(legacy, requested_employee_no="0019336")
    assert raised.value.status_code == 409
    assert "re-verify" in raised.value.message.lower()


def test_fresh_registration_identity_uses_identifiers_not_name_or_dob():
    loan = SimpleNamespace(
        borrower=SimpleNamespace(
            user=SimpleNamespace(
                person=SimpleNamespace(national_id="042271207029")
            )
        )
    )
    _validate_fresh_exact_identity(
        loan,
        employee_no="0019336",
        employee_details={
            "EmployeeNo": "0019336",
            "Name": "DISPLAY NAME CAN DIFFER",
            "Surname": "DISPLAY ONLY",
            "DOB": "01/01/1900",
        },
    )


def test_fresh_registration_rejects_provider_national_id_conflict():
    loan = SimpleNamespace(
        borrower=SimpleNamespace(
            user=SimpleNamespace(
                person=SimpleNamespace(national_id="042271207029")
            )
        )
    )
    with pytest.raises(CdasLifecycleError) as raised:
        _validate_fresh_exact_identity(
            loan,
            employee_no="0019336",
            employee_details={
                "EmployeeNo": "0019336",
                "NationalID": "042271207028",
            },
        )
    assert raised.value.status_code == 409
