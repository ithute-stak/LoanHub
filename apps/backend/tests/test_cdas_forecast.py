from __future__ import annotations

from datetime import date

import pytest

from services.cdas_forecast import build_cdas_forecast


TODAY = date(2026, 9, 15)


def _row(
    *,
    agency: str,
    amount: float,
    booking_open_date: str | None,
    booking_status: str = "UPCOMING",
    active: bool = True,
    own: bool = False,
    excluded: bool = False,
    quality: str = "OK",
) -> dict:
    return {
        "agency_name": agency,
        "deduction_amount": amount,
        "booking_open_date": booking_open_date,
        "booking_status": booking_status,
        "reported_active": active,
        "is_own_booking": own,
        "excluded_from_booking": excluded,
        "data_quality_status": quality,
    }


def test_forecast_separates_book_now_and_monthly_horizon() -> None:
    profiles = [
        {
            "client_key": "client-a",
            "employer": "Employer One",
            "current_deductions": [
                _row(agency="Agency Alpha", amount=1000, booking_open_date="2026-09-10", booking_status="BOOK_NOW"),
                _row(agency="Agency Alpha", amount=500, booking_open_date="2026-10-01"),
            ],
        },
        {
            "client_key": "client-b",
            "employer": "Employer Two",
            "current_deductions": [
                _row(agency="Agency Beta", amount=2000, booking_open_date="2026-11-20"),
                _row(agency="Agency Beta", amount=750, booking_open_date="2027-03-01"),
            ],
        },
    ]

    result = build_cdas_forecast(profiles, today=TODAY, horizon_months=12)

    assert result["summary"]["book_now_count"] == 1
    assert result["summary"]["book_now_value"] == 1000
    assert result["summary"]["book_now_client_count"] == 1
    assert result["summary"]["scheduled_count"] == 3
    assert result["summary"]["scheduled_value"] == 3250
    assert result["summary"]["scheduled_client_count"] == 2
    assert result["summary"]["next_3_months"] == {
        "opportunity_count": 2,
        "monthly_deduction_value": 2500.0,
    }
    assert result["summary"]["next_6_months"] == {
        "opportunity_count": 3,
        "monthly_deduction_value": 3250.0,
    }
    assert result["summary"]["peak_month"] == "2026-11"
    assert result["summary"]["peak_month_value"] == 2000

    months = {item["month"]: item for item in result["months"]}
    assert months["2026-10"]["monthly_deduction_value"] == 500
    assert months["2026-11"]["monthly_deduction_value"] == 2000
    assert months["2027-03"]["monthly_deduction_value"] == 750


def test_forecast_excludes_inactive_own_and_bad_quality_from_opportunity_windows() -> None:
    profiles = [
        {
            "client_key": "client-a",
            "employer": "Employer One",
            "current_deductions": [
                _row(agency="Own Agency", amount=900, booking_open_date="2026-10-01", own=True),
                _row(agency="Inactive Agency", amount=800, booking_open_date="2026-10-01", active=False),
                _row(agency="Bad Agency", amount=700, booking_open_date="2026-10-01", excluded=True, quality="MISSING_EXPIRY"),
                _row(agency="Conflict Agency", amount=600, booking_open_date="2026-11-01", quality="DATE_CONFLICT"),
            ],
        }
    ]

    result = build_cdas_forecast(profiles, today=TODAY, horizon_months=12)

    assert result["summary"]["scheduled_count"] == 0
    assert result["summary"]["scheduled_value"] == 0
    assert result["summary"]["book_now_count"] == 0
    assert result["summary"]["excluded_quality_count"] == 2
    assert result["summary"]["excluded_quality_value"] == 1300
    assert result["top_employers"] == []
    assert result["top_agencies"] == []


def test_forecast_tracks_unscheduled_later_and_missing_employer_without_fake_months() -> None:
    profiles = [
        {
            "client_key": "client-a",
            "employer": None,
            "current_deductions": [
                _row(agency="Agency A", amount=300, booking_open_date=None),
                _row(agency="Agency B", amount=400, booking_open_date="2027-10-01"),
            ],
        }
    ]

    result = build_cdas_forecast(profiles, today=TODAY, horizon_months=12)

    assert result["summary"]["unscheduled_count"] == 1
    assert result["summary"]["unscheduled_value"] == 300
    assert result["summary"]["later_known_count"] == 1
    assert result["summary"]["later_known_value"] == 400
    assert result["summary"]["missing_employer_client_count"] == 1
    assert result["summary"]["scheduled_count"] == 0
    assert result["summary"]["peak_month"] is None


def test_forecast_concentrations_are_aggregate_only_and_case_insensitive() -> None:
    profiles = [
        {
            "client_key": "client-a",
            "client_name": "Secret Client A",
            "client_reference": "REF-A",
            "employer": "Ministry of Works",
            "current_deductions": [
                _row(agency="Agency Alpha", amount=1000, booking_open_date="2026-09-01", booking_status="BOOK_NOW"),
            ],
        },
        {
            "client_key": "client-b",
            "client_name": "Secret Client B",
            "client_reference": "REF-B",
            "employer": "ministry of works",
            "current_deductions": [
                _row(agency="agency alpha", amount=500, booking_open_date="2026-10-01"),
            ],
        },
    ]

    result = build_cdas_forecast(profiles, today=TODAY, horizon_months=12)

    assert len(result["top_employers"]) == 1
    assert result["top_employers"][0]["total_opportunity_value"] == 1500
    assert len(result["top_agencies"]) == 1
    assert result["top_agencies"][0]["total_opportunity_value"] == 1500

    rendered = repr(result)
    assert "Secret Client A" not in rendered
    assert "Secret Client B" not in rendered
    assert "REF-A" not in rendered
    assert "REF-B" not in rendered
    assert "client-a" not in rendered
    assert "client-b" not in rendered


def test_forecast_horizon_must_be_between_one_and_twenty_four_months() -> None:
    with pytest.raises(ValueError, match="between 1 and 24 months"):
        build_cdas_forecast([], today=TODAY, horizon_months=0)
    with pytest.raises(ValueError, match="between 1 and 24 months"):
        build_cdas_forecast([], today=TODAY, horizon_months=25)
