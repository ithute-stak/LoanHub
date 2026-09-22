from services.cdas_analysis_history import analysis_fingerprint
from services.cdas_official_snapshot import normalize_official_cdas_snapshot


def _raw_snapshot(*, checked_at: str) -> dict:
    return {
        "source": "CDAS_API",
        "checked_at": checked_at,
        "employee": {
            "EmployeeNo": "EMP-001",
            "Name": "Mpho",
            "Surname": "Mokoena",
            "DOB": "1990-01-02",
            "Department": "Finance",
            "JoiningDate": "2020-03-01",
            "TerminationDate": None,
        },
        "affordability": 1250.50,
        "deductions": [
            {
                "EmployeeNo": "EMP-001",
                "DeductionType": 1,
                "DeductionAmount": 350.25,
                "DeductionStatus": 5,
            },
            {
                "EmployeeNo": "EMP-001",
                "DeductionType": 1,
                "DeductionAmount": 100.00,
                "DeductionStatus": 7,
            },
        ],
        "own_deductions": [
            {
                "DeductionID": 77,
                "EmployeeNo": "EMP-001",
                "ItemCode": "ITEM-1",
                "ReferenceNo": "REF-1",
                "DeductionAmount": 50,
                "DeductionStatus": 5,
            }
        ],
    }


def _fingerprint(snapshot: dict) -> str:
    return analysis_fingerprint(
        snapshot,
        client_name="Mpho Mokoena",
        client_reference="EMP-001",
    )


def test_normalizes_official_snapshot_without_inventing_booking_approval():
    snapshot = normalize_official_cdas_snapshot(
        _raw_snapshot(checked_at="2026-09-22T10:00:00+00:00"),
        own_deduction_status=5,
    )

    assert snapshot["source"] == "CDAS_API"
    assert snapshot["source_version"] == "1.5"
    assert snapshot["profile"]["employee_no"] == "EMP-001"
    assert snapshot["profile"]["full_name"] == "Mpho Mokoena"
    assert snapshot["profile"]["department"] == "Finance"
    assert snapshot["profile"]["employer"] is None
    assert snapshot["capacity"]["assessed_available_amount"] == 1250.50
    assert snapshot["capacity"]["booking_allowed"] is False
    assert snapshot["decision"] == "REVIEW_REQUIRED"
    assert snapshot["reported_active_monthly_deductions"] == 350.25
    assert snapshot["total_monthly_deductions"] == 450.25
    assert snapshot["own_monthly_deductions"] == 50.0
    assert snapshot["official_api"]["own_deduction_status"] == 5
    assert "checked_at" not in snapshot


def test_refresh_timestamp_does_not_create_a_new_analysis_fingerprint():
    first = normalize_official_cdas_snapshot(
        _raw_snapshot(checked_at="2026-09-22T10:00:00+00:00"),
        own_deduction_status=5,
    )
    second = normalize_official_cdas_snapshot(
        _raw_snapshot(checked_at="2026-09-22T10:05:00+00:00"),
        own_deduction_status=5,
    )

    assert _fingerprint(first) == _fingerprint(second)


def test_provider_row_order_does_not_create_a_new_analysis_fingerprint():
    first_raw = _raw_snapshot(checked_at="2026-09-22T10:00:00+00:00")
    second_raw = _raw_snapshot(checked_at="2026-09-22T10:05:00+00:00")
    second_raw["deductions"] = list(reversed(second_raw["deductions"]))

    first = normalize_official_cdas_snapshot(first_raw, own_deduction_status=5)
    second = normalize_official_cdas_snapshot(second_raw, own_deduction_status=5)

    assert _fingerprint(first) == _fingerprint(second)


def test_changed_cdas_data_creates_a_new_fingerprint():
    first = normalize_official_cdas_snapshot(
        _raw_snapshot(checked_at="2026-09-22T10:00:00+00:00"),
        own_deduction_status=5,
    )
    changed_raw = _raw_snapshot(checked_at="2026-09-22T10:05:00+00:00")
    changed_raw["affordability"] = 900.0
    second = normalize_official_cdas_snapshot(changed_raw, own_deduction_status=5)

    assert _fingerprint(first) != _fingerprint(second)
