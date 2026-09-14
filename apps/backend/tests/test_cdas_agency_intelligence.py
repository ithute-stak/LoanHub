from datetime import date

from services.cdas_agency_intelligence import build_agency_intelligence


TODAY = date(2026, 9, 14)


def _row(
    agency: str,
    amount: float,
    *,
    item_code: str,
    own: bool = False,
    booking_date: str | None = None,
    booking_status: str = "WAIT",
    quality_status: str = "OK",
    excluded: bool = False,
) -> dict:
    return {
        "agency_name": agency,
        "deduction_amount": amount,
        "item_code": item_code,
        "reported_active": True,
        "is_own_booking": own,
        "booking_open_date": booking_date,
        "booking_status": booking_status,
        "data_quality_status": quality_status,
        "excluded_from_booking": excluded,
    }


def test_agency_intelligence_aggregates_latest_profile_deductions_without_client_details():
    profiles = [
        {
            "client_key": "client-1",
            "current_deductions": [
                _row("Lesana", 1000, item_code="2561", booking_date="2026-09-14", booking_status="BOOK_NOW"),
                _row("Our Agency", 500, item_code="9000", own=True),
            ],
        },
        {
            "client_key": "client-2",
            "current_deductions": [
                _row("Lesana", 2000, item_code="2561", booking_date="2026-10-10"),
                _row("ABC Finance", 3000, item_code="3001", booking_date="2026-12-01"),
                _row(
                    "ABC Finance",
                    700,
                    item_code="3002",
                    booking_date="2026-09-20",
                    quality_status="DATE_CONFLICT",
                    excluded=True,
                ),
            ],
        },
    ]

    result = build_agency_intelligence(profiles, today=TODAY)

    assert result["summary"] == {
        "agency_count": 3,
        "client_count": 2,
        "active_deduction_count": 5,
        "active_monthly_value": 7200.0,
        "own_monthly_value": 500.0,
        "competitor_monthly_value": 6700.0,
        "book_now_count": 1,
        "book_now_value": 1000.0,
        "next_30_days_count": 2,
        "next_30_days_value": 3000.0,
        "next_90_days_count": 3,
        "next_90_days_value": 6000.0,
    }

    assert [item["agency_name"] for item in result["items"]] == [
        "ABC Finance",
        "Lesana",
        "Our Agency",
    ]

    abc = result["items"][0]
    assert abc["competitor_monthly_value"] == 3700.0
    assert abc["data_quality_issue_count"] == 1
    assert abc["next_90_days_value"] == 3000.0
    assert abc["earliest_competitor_booking_date"] == "2026-12-01"

    lesana = result["items"][1]
    assert lesana["client_count"] == 2
    assert lesana["book_now_value"] == 1000.0
    assert lesana["next_30_days_value"] == 3000.0
    assert lesana["competitor_value_share_percent"] == 44.78

    forbidden = {"client_name", "client_reference", "employee_no", "nid"}
    for item in result["items"]:
        assert forbidden.isdisjoint(item.keys())


def test_inactive_deductions_do_not_enter_agency_totals():
    profiles = [
        {
            "client_key": "client-1",
            "current_deductions": [
                {
                    **_row("Dormant Agency", 5000, item_code="1000"),
                    "reported_active": False,
                },
                _row("Live Agency", 600, item_code="2000"),
            ],
        }
    ]

    result = build_agency_intelligence(profiles, today=TODAY)

    assert result["summary"]["agency_count"] == 1
    assert result["summary"]["active_monthly_value"] == 600.0
    assert result["items"][0]["agency_name"] == "Live Agency"


def test_invalid_competitor_row_counts_financially_but_cannot_create_booking_opportunity():
    profiles = [
        {
            "client_key": "client-1",
            "current_deductions": [
                _row(
                    "Conflict Agency",
                    1200,
                    item_code="4000",
                    booking_date="2026-09-15",
                    booking_status="BOOK_NOW",
                    quality_status="DATE_CONFLICT",
                    excluded=True,
                )
            ],
        }
    ]

    item = build_agency_intelligence(profiles, today=TODAY)["items"][0]

    assert item["active_monthly_value"] == 1200.0
    assert item["competitor_monthly_value"] == 1200.0
    assert item["data_quality_issue_count"] == 1
    assert item["book_now_count"] == 0
    assert item["next_30_days_count"] == 0
    assert item["next_90_days_count"] == 0
    assert item["earliest_competitor_booking_date"] is None
