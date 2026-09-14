from datetime import date

from services.cdas_booking_priority import build_booking_priority_queue, score_booking_priority


TODAY = date(2026, 9, 14)


def _opportunity(
    identifier: str,
    booking_date: str | None,
    *,
    state: str = "UPCOMING",
    deduction: float = 500.0,
    decision: str = "WAIT_UNTIL",
    booking_allowed: bool = False,
    capacity: float | None = 0.0,
    quality_issues: int = 0,
) -> dict:
    return {
        "id": identifier,
        "client_name": f"Client {identifier}",
        "client_reference": f"EMP-{identifier}",
        "status": "booked" if state == "BOOKED" else "monitoring",
        "state": state,
        "booking_open_date": booking_date,
        "opportunity_agency_name": "Example Agency",
        "opportunity_reference_no": f"REF-{identifier}",
        "opportunity_expiry_date": "2027-12-31",
        "opportunity_deduction_amount": deduction,
        "analysis_snapshot": {
            "decision": decision,
            "data_quality_issue_count": quality_issues,
            "capacity": {
                "booking_allowed": booking_allowed,
                "assessed_available_amount": capacity,
            },
            "booking_term": {
                "amount_owing": 12000,
                "months_required": 6,
            },
        },
    }


def test_overdue_high_value_ready_clean_opportunity_can_score_100():
    item = _opportunity(
        "top",
        "2026-08-15",
        state="BOOK_NOW",
        deduction=5000,
        decision="BOOK_NOW",
        booking_allowed=True,
        capacity=6000,
    )

    priority = score_booking_priority(item, today=TODAY)

    assert priority["score"] == 100
    assert priority["band"] == "CRITICAL"
    assert priority["components"] == {
        "urgency": 50,
        "value": 20,
        "readiness": 20,
        "quality": 10,
    }


def test_far_future_small_opportunity_stays_low_priority():
    item = _opportunity("future", "2026-12-31", deduction=200, capacity=0)

    priority = score_booking_priority(item, today=TODAY)

    assert priority["score"] == 28
    assert priority["band"] == "LOW"
    assert priority["components"]["urgency"] == 5
    assert priority["components"]["value"] == 5
    assert priority["components"]["readiness"] == 8
    assert priority["components"]["quality"] == 10


def test_data_quality_issue_reduces_score_and_adds_warning():
    clean = _opportunity("clean", "2026-09-20", deduction=1500, quality_issues=0)
    issue = _opportunity("issue", "2026-09-20", deduction=1500, quality_issues=1)

    clean_priority = score_booking_priority(clean, today=TODAY)
    issue_priority = score_booking_priority(issue, today=TODAY)

    assert clean_priority["score"] - issue_priority["score"] == 6
    assert issue_priority["components"]["quality"] == 4
    assert any("data-quality issue" in warning for warning in issue_priority["warnings"])


def test_review_required_blocks_readiness_points_even_when_capacity_flag_is_true():
    item = _opportunity(
        "review",
        "2026-09-14",
        state="BOOK_NOW",
        deduction=2500,
        decision="REVIEW_REQUIRED",
        booking_allowed=True,
        capacity=3000,
    )

    priority = score_booking_priority(item, today=TODAY)

    assert priority["components"]["readiness"] == 0
    assert any("requires review" in warning for warning in priority["warnings"])


def test_booked_records_have_zero_priority():
    item = _opportunity(
        "booked",
        "2026-08-01",
        state="BOOKED",
        deduction=9000,
        decision="ALREADY_BOOKED",
        booking_allowed=True,
        capacity=9000,
    )

    priority = score_booking_priority(item, today=TODAY)

    assert priority["score"] == 0
    assert priority["band"] == "BOOKED"
    assert priority["components"] == {"urgency": 0, "value": 0, "readiness": 0, "quality": 0}


def test_priority_queue_sorts_open_work_highest_first_and_summarizes_value():
    items = [
        _opportunity("low", "2026-12-31", deduction=200),
        _opportunity("critical", "2026-08-01", state="BOOK_NOW", deduction=5000, decision="BOOK_NOW", booking_allowed=True, capacity=7000),
        _opportunity("booked", "2026-08-01", state="BOOKED", deduction=8000, decision="ALREADY_BOOKED"),
    ]

    queue = build_booking_priority_queue(items, today=TODAY)

    assert [item["id"] for item in queue["items"]] == ["critical", "low", "booked"]
    assert queue["summary"]["critical"] == 1
    assert queue["summary"]["low"] == 1
    assert queue["summary"]["booked"] == 1
    assert queue["summary"]["open"] == 2
    assert queue["summary"]["monthly_deduction_value"] == 5200.0


def test_unscheduled_record_gets_warning_instead_of_fake_urgency():
    item = _opportunity("missing", None, deduction=1000)

    priority = score_booking_priority(item, today=TODAY)

    assert priority["components"]["urgency"] == 0
    assert any("Booking date is missing" in warning for warning in priority["warnings"])
    assert 0 <= priority["score"] <= 100
