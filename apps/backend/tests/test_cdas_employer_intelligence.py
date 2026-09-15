from datetime import date

from services.cdas_employer_intelligence import build_employer_intelligence


def _deduction(
    *,
    amount=1000.0,
    agency="Competitor Bank",
    active=True,
    own=False,
    booking_status="WAIT",
    booking_open_date="2026-10-01",
    excluded=False,
    quality="OK",
):
    return {
        "agency_name": agency,
        "deduction_amount": amount,
        "reported_active": active,
        "is_own_booking": own,
        "booking_status": booking_status,
        "booking_open_date": booking_open_date,
        "excluded_from_booking": excluded,
        "data_quality_status": quality,
    }


def _profile(*, employer="Ministry of Finance", capacity=500.0, decision="WAIT_UNTIL", issues=0, deductions=None):
    return {
        "employer": employer,
        "assessed_available_amount": capacity,
        "decision": decision,
        "data_quality_issue_count": issues,
        "current_deductions": deductions if deductions is not None else [_deduction()],
    }


def test_same_employer_is_grouped_case_insensitively():
    result = build_employer_intelligence(
        [
            _profile(employer="Ministry of Finance", deductions=[_deduction(amount=1000)]),
            _profile(employer=" ministry of finance ", deductions=[_deduction(amount=500)]),
        ],
        today=date(2026, 9, 15),
    )

    assert result["summary"]["employer_count"] == 1
    item = result["items"][0]
    assert item["client_count"] == 2
    assert item["active_monthly_value"] == 1500.0
    assert item["competitor_monthly_value"] == 1500.0


def test_inactive_deductions_do_not_inflate_employer_totals():
    result = build_employer_intelligence(
        [_profile(deductions=[_deduction(amount=900, active=True), _deduction(amount=4000, active=False)])],
        today=date(2026, 9, 15),
    )
    item = result["items"][0]

    assert item["active_deduction_count"] == 1
    assert item["active_monthly_value"] == 900.0


def test_invalid_active_competitor_stays_in_financial_totals_but_not_opportunities():
    result = build_employer_intelligence(
        [_profile(deductions=[_deduction(amount=1200, booking_status="BOOK_NOW", booking_open_date="2026-09-01", excluded=True, quality="MISSING_EXPIRY")])],
        today=date(2026, 9, 15),
    )
    item = result["items"][0]

    assert item["competitor_monthly_value"] == 1200.0
    assert item["book_now_count"] == 0
    assert item["book_now_value"] == 0.0
    assert item["next_90_days_value"] == 0.0


def test_own_deductions_are_visible_financially_but_not_competitor_opportunities():
    result = build_employer_intelligence(
        [_profile(deductions=[_deduction(amount=700, own=True, booking_status="BOOK_NOW", booking_open_date="2026-09-01")])],
        today=date(2026, 9, 15),
    )
    item = result["items"][0]

    assert item["active_monthly_value"] == 700.0
    assert item["own_monthly_value"] == 700.0
    assert item["competitor_monthly_value"] == 0.0
    assert item["book_now_count"] == 0


def test_booking_windows_capacity_decisions_and_quality_are_aggregated():
    result = build_employer_intelligence(
        [
            _profile(capacity=800, decision="BOOK_NOW", issues=2, deductions=[_deduction(amount=1000, booking_status="BOOK_NOW", booking_open_date="2026-09-10")]),
            _profile(capacity=-50, decision="WAIT_UNTIL", issues=0, deductions=[_deduction(amount=600, booking_open_date="2026-10-10")]),
        ],
        today=date(2026, 9, 15),
    )
    item = result["items"][0]

    assert item["book_now_count"] == 1
    assert item["book_now_value"] == 1000.0
    assert item["next_30_days_count"] == 1
    assert item["next_30_days_value"] == 600.0
    assert item["available_capacity_total"] == 800.0
    assert item["capacity_known_count"] == 2
    assert item["no_headroom_count"] == 1
    assert item["decision_counts"] == {"BOOK_NOW": 1, "WAIT_UNTIL": 1}
    assert item["data_quality_client_count"] == 1
    assert item["data_quality_issue_count"] == 2


def test_missing_employer_clients_are_counted_but_not_exposed_as_fake_employer():
    result = build_employer_intelligence(
        [_profile(employer=None), _profile(employer="")],
        today=date(2026, 9, 15),
    )

    assert result["summary"]["missing_employer_clients"] == 2
    assert result["summary"]["employer_count"] == 0
    assert result["items"] == []


def test_employer_items_sort_by_immediate_then_90_day_opportunity_value():
    result = build_employer_intelligence(
        [
            _profile(employer="Later Employer", deductions=[_deduction(amount=5000, booking_open_date="2026-10-15")]),
            _profile(employer="Book Now Employer", deductions=[_deduction(amount=1000, booking_status="BOOK_NOW", booking_open_date="2026-09-01")]),
        ],
        today=date(2026, 9, 15),
    )

    assert [item["employer_name"] for item in result["items"]] == ["Book Now Employer", "Later Employer"]
