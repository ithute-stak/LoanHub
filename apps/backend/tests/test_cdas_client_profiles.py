from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from database.models.cdas_booking import CdasAnalysisRecord
from services.cdas_client_profiles import build_client_profiles


def _record(
    *,
    client_name: str = "Thabo Mokoena",
    client_reference: str | None = "EMP-001",
    employee_no: str | None = "EMP-001",
    nid: str | None = "NID-001",
    employer: str | None = "Ministry of Finance",
    analyzed_at: datetime,
    decision: str = "WAIT_UNTIL",
    capacity: str = "500.00",
    next_booking: date | None = date(2026, 12, 1),
    agency_name: str = "First National Bank of Lesotho",
) -> CdasAnalysisRecord:
    snapshot = {
        "profile": {
            "employee_no": employee_no,
            "nid": nid,
            "full_name": client_name,
            "employer": employer,
        },
        "application_context": {
            "current_cdas_agency_code": "2595",
            "current_cdas_agency_name": agency_name,
        },
        "capacity": {"assessed_available_amount": float(capacity)},
        "booking_term": {"amount_owing": 2000.0, "months_required": 4},
        "decision": decision,
        "next_possible_booking_date": next_booking.isoformat() if next_booking else None,
        "reported_active_monthly_deductions": 1500.0,
        "total_monthly_deductions": 1500.0,
        "data_quality_issue_count": 0,
        "deductions": [
            {
                "item_code": "2595",
                "agency_name": agency_name,
                "reference_no": "FNB-001",
                "deduction_amount": 500.0,
                "effective_date": "2026-01-01",
                "expiry_date": "2027-01-01",
                "booking_status": "WAIT",
                "data_quality_status": "OK",
            }
        ],
    }
    record = CdasAnalysisRecord(
        id=uuid4(),
        company_id=uuid4(),
        client_name=client_name,
        client_reference=client_reference,
        employee_no=employee_no,
        nid=nid,
        employer=employer,
        current_agency_code="2595",
        current_agency_name=agency_name,
        decision=decision,
        assessed_available_amount=Decimal(capacity),
        amount_owing=Decimal("2000.00"),
        booking_months=4,
        next_possible_booking_date=next_booking,
        reported_active_monthly_deductions=Decimal("1500.00"),
        total_monthly_deductions=Decimal("1500.00"),
        data_quality_issue_count=0,
        analysis_fingerprint=uuid4().hex + uuid4().hex,
        analysis_snapshot=snapshot,
        analyzed_by_name="Loan Officer",
        analyzed_by_role="company_user",
    )
    record.created_at = analyzed_at
    record.updated_at = analyzed_at
    return record


def test_same_exact_identity_builds_one_profile_with_latest_analysis_values():
    older = _record(
        analyzed_at=datetime(2026, 9, 10, 9, 0),
        capacity="300.00",
        decision="WAIT_UNTIL",
    )
    newer = _record(
        analyzed_at=datetime(2026, 9, 14, 11, 0),
        capacity="750.00",
        decision="BOOK_NOW",
    )

    profiles = build_client_profiles([older, newer], [])

    assert len(profiles) == 1
    profile = profiles[0]
    assert profile["analysis_count"] == 2
    assert profile["decision"] == "BOOK_NOW"
    assert profile["assessed_available_amount"] == Decimal("750.00")
    assert profile["latest_analysis_id"] == str(newer.id)
    assert profile["employee_no"] == "EMP-001"


def test_identity_aliases_bridge_reference_changes_when_employee_number_matches():
    older = _record(
        analyzed_at=datetime(2026, 9, 10, 9, 0),
        client_reference="OLD-REF",
        employee_no="EMP-777",
        nid="NID-777",
    )
    newer = _record(
        analyzed_at=datetime(2026, 9, 14, 11, 0),
        client_reference="NEW-REF",
        employee_no="EMP-777",
        nid="NID-777",
    )

    profiles = build_client_profiles([older, newer], [])

    assert len(profiles) == 1
    assert profiles[0]["analysis_count"] == 2
    assert profiles[0]["client_reference"] == "NEW-REF"


def test_different_exact_identities_remain_separate_profiles():
    first = _record(analyzed_at=datetime(2026, 9, 14, 8, 0))
    second = _record(
        analyzed_at=datetime(2026, 9, 14, 9, 0),
        client_name="Lerato Thabo",
        client_reference="EMP-002",
        employee_no="EMP-002",
        nid="NID-002",
    )

    profiles = build_client_profiles([first, second], [])

    assert len(profiles) == 2
    assert len({profile["client_key"] for profile in profiles}) == 2


def test_same_name_without_employer_is_not_guessed_as_same_person():
    first = _record(
        analyzed_at=datetime(2026, 9, 14, 8, 0),
        client_reference=None,
        employee_no=None,
        nid=None,
        employer=None,
    )
    second = _record(
        analyzed_at=datetime(2026, 9, 14, 9, 0),
        client_reference=None,
        employee_no=None,
        nid=None,
        employer=None,
    )

    profiles = build_client_profiles([first, second], [])

    assert len(profiles) == 2
    assert len({profile["client_key"] for profile in profiles}) == 2


def test_detail_uses_latest_deductions_and_orders_analysis_history_newest_first():
    older = _record(
        analyzed_at=datetime(2026, 9, 10, 9, 0),
        agency_name="Lesana Lesotho Limited",
    )
    newer = _record(
        analyzed_at=datetime(2026, 9, 14, 11, 0),
        agency_name="First National Bank of Lesotho",
    )

    profiles = build_client_profiles([older, newer], [], include_detail=True)

    profile = profiles[0]
    assert profile["current_deductions"][0]["agency_name"] == "First National Bank of Lesotho"
    assert [item["id"] for item in profile["analyses"]] == [str(newer.id), str(older.id)]
    assert profile["profile"]["employee_no"] == "EMP-001"
