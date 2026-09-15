from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from services.cdas_change_detection import build_change_detection, detect_analysis_changes


NOW = datetime(2026, 9, 15, 8, 0, 0)


def _record(*, created_at=NOW, client_reference="EMP-100", snapshot=None, **overrides):
    values = {
        "id": uuid4(),
        "created_at": created_at,
        "analysis_snapshot": snapshot or {
            "profile": {"full_name": "Mpho Client", "employee_no": "EMP-100", "employer": "Ministry A"},
            "capacity": {"assessed_available_amount": 1000},
            "application_context": {"current_cdas_agency_name": "Batlokoa"},
            "booking_term": {"amount_owing": 5000, "months_required": 5},
            "own_monthly_deductions": 100,
            "competitor_monthly_deductions": 900,
            "data_quality_issue_count": 0,
            "deductions": [],
        },
        "client_name": "Mpho Client",
        "client_reference": client_reference,
        "employee_no": client_reference,
        "nid": None,
        "employer": "Ministry A",
        "current_agency_code": "3000",
        "current_agency_name": "Batlokoa",
        "decision": "WAIT_UNTIL",
        "assessed_available_amount": Decimal("1000.00"),
        "amount_owing": Decimal("5000.00"),
        "booking_months": 5,
        "next_possible_booking_date": date(2026, 10, 1),
        "reported_active_monthly_deductions": Decimal("1000.00"),
        "total_monthly_deductions": Decimal("1000.00"),
        "data_quality_issue_count": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _deduction(*, reference="REF-1", amount=500, expiry="2027-01-31", agency="Agency A", item="2561"):
    return {
        "item_code": item,
        "agency_name": agency,
        "reference_no": reference,
        "deduction_amount": amount,
        "status": "Active",
        "effective_date": "2025-01-01",
        "expiry_date": expiry,
        "booking_open_date": "2026-07-31",
        "data_quality_status": "OK",
    }


def test_detects_material_field_changes_with_before_and_after_values():
    previous = _record()
    latest = _record(
        created_at=NOW + timedelta(days=1),
        decision="BOOK_NOW",
        assessed_available_amount=Decimal("1500.00"),
        next_possible_booking_date=date(2026, 9, 15),
    )

    changes = detect_analysis_changes(previous, latest)
    by_field = {change["field"]: change for change in changes if change["kind"] == "FIELD_CHANGED"}

    assert by_field["decision"]["before"] == "WAIT_UNTIL"
    assert by_field["decision"]["after"] == "BOOK_NOW"
    assert by_field["decision"]["impact"] == "MATERIAL"
    assert by_field["assessed_available_amount"]["before"] == Decimal("1000.00")
    assert by_field["assessed_available_amount"]["after"] == Decimal("1500.00")
    assert by_field["next_possible_booking_date"]["after"] == "2026-09-15"


def test_detects_added_removed_and_modified_deductions():
    previous_snapshot = _record().analysis_snapshot.copy()
    previous_snapshot["deductions"] = [
        _deduction(reference="KEEP", amount=500, expiry="2027-01-31"),
        _deduction(reference="REMOVE", amount=700),
    ]
    latest_snapshot = _record().analysis_snapshot.copy()
    latest_snapshot["deductions"] = [
        _deduction(reference="KEEP", amount=650, expiry="2027-03-31"),
        _deduction(reference="ADD", amount=900, agency="Agency B"),
    ]

    changes = detect_analysis_changes(
        _record(snapshot=previous_snapshot),
        _record(created_at=NOW + timedelta(days=1), snapshot=latest_snapshot),
    )
    kinds = [change["kind"] for change in changes]

    assert "DEDUCTION_ADDED" in kinds
    assert "DEDUCTION_REMOVED" in kinds
    assert "DEDUCTION_MODIFIED" in kinds
    modified = next(change for change in changes if change["kind"] == "DEDUCTION_MODIFIED")
    assert set(modified["changed_fields"]) == {"deduction_amount", "expiry_date"}


def test_no_tracked_change_returns_empty_change_list():
    snapshot = _record().analysis_snapshot
    previous = _record(snapshot=snapshot)
    latest = _record(created_at=NOW + timedelta(days=1), snapshot=snapshot)
    assert detect_analysis_changes(previous, latest) == []


def test_change_detection_compares_only_exact_group_with_two_versions():
    previous = _record(created_at=NOW - timedelta(days=2), client_reference="EMP-101")
    latest = _record(created_at=NOW - timedelta(days=1), client_reference="EMP-101", decision="BOOK_NOW")
    one_version = _record(client_reference="EMP-202", client_name="Other Client", employee_no="EMP-202")

    result = build_change_detection([latest, previous, one_version])

    assert result["summary"]["clients_compared"] == 1
    assert result["items"][0]["client_reference"] == "EMP-101"
    assert result["items"][0]["change_count"] == 1
    assert result["summary"]["clients_with_material_changes"] == 1


def test_uncertain_anonymous_analyses_are_not_merged_for_change_detection():
    first = _record(client_reference=None, employee_no=None, client_name="Same Name", employer=None)
    first.analysis_snapshot = {"profile": {"full_name": "Same Name"}, "deductions": []}
    second = _record(created_at=NOW + timedelta(days=1), client_reference=None, employee_no=None, client_name="Same Name", employer=None)
    second.analysis_snapshot = {"profile": {"full_name": "Same Name"}, "deductions": []}

    result = build_change_detection([first, second])

    assert result["summary"]["clients_compared"] == 0
    assert result["items"] == []
