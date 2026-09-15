from datetime import datetime, timedelta

from services.cdas_officer_performance import build_officer_performance


def _opportunity(
    identifier: str,
    *,
    assigned: str | None = None,
    state: str = "UPCOMING",
    amount: float = 100,
    booked_by: str | None = None,
) -> dict:
    return {
        "id": identifier,
        "client_name": f"Client {identifier}",
        "client_reference": identifier,
        "state": state,
        "pipeline_stage": state.lower(),
        "assigned_to_user_id": assigned,
        "opportunity_deduction_amount": amount,
        "booked_by_user_id": booked_by,
        "booking_open_date": "2026-10-01",
    }


def test_officer_metrics_use_current_assignment_and_authored_activity() -> None:
    now = datetime(2026, 9, 15, 10, 0)
    staff = [
        {"user_id": "u1", "name": "Officer One", "role": "officer", "is_active": True},
        {"user_id": "u2", "name": "Officer Two", "role": "officer", "is_active": True},
    ]
    opportunities = [
        _opportunity("a", assigned="u1", state="BOOK_NOW", amount=400),
        _opportunity("b", assigned="u1", state="UPCOMING", amount=600),
        _opportunity("c", assigned="u1", state="BOOKED", amount=300, booked_by="u1"),
        _opportunity("d", assigned="u1", state="FAILED", amount=200),
        _opportunity("e", assigned=None, state="UPCOMING", amount=500),
    ]
    contacts = [
        {
            "opportunity_id": "a",
            "created_by_user_id": "u1",
            "channel": "call",
            "outcome": "call_back",
            "contacted_at": now - timedelta(days=10),
            "next_follow_up_at": now - timedelta(days=2),
        },
        # The newest contact supersedes the older overdue instruction.
        {
            "opportunity_id": "a",
            "created_by_user_id": "u2",
            "channel": "whatsapp",
            "outcome": "interested",
            "contacted_at": now - timedelta(days=1),
            "next_follow_up_at": now + timedelta(days=2),
        },
        {
            "opportunity_id": "b",
            "created_by_user_id": "u1",
            "channel": "email",
            "outcome": "documents_requested",
            "contacted_at": now - timedelta(days=40),
            "next_follow_up_at": None,
        },
    ]
    failures = [
        {
            "opportunity_id": "d",
            "created_by_user_id": "u1",
            "failed_at": now - timedelta(days=5),
        }
    ]

    result = build_officer_performance(staff, opportunities, contacts, failures, now=now)
    one = next(item for item in result["officers"] if item["user_id"] == "u1")
    two = next(item for item in result["officers"] if item["user_id"] == "u2")

    assert one["assigned_total"] == 4
    assert one["open_assigned"] == 2
    assert one["book_now_assigned"] == 1
    assert one["open_monthly_deduction_value"] == 1000
    assert one["overdue_follow_ups"] == 0
    assert one["scheduled_follow_ups"] == 1
    assert one["uncontacted_open"] == 0
    assert one["contacts_total"] == 2
    assert one["contacts_last_30_days"] == 1
    assert one["booked_assigned"] == 1
    assert one["failed_assigned"] == 1
    assert one["booked_by_officer"] == 1
    assert one["failures_reported_last_30_days"] == 1
    assert two["contacts_last_30_days"] == 1
    assert result["summary"]["unassigned_open"] == 1


def test_inactive_staff_remain_visible_and_closed_work_is_not_unassigned() -> None:
    now = datetime(2026, 9, 15, 10, 0)
    staff = [
        {"user_id": "active", "name": "Active", "is_active": True},
        {"user_id": "inactive", "name": "Inactive", "is_active": False},
    ]
    opportunities = [
        _opportunity("old", assigned="inactive", state="UPCOMING"),
        _opportunity("open", assigned=None, state="BOOK_NOW"),
        _opportunity("booked", assigned=None, state="BOOKED"),
        _opportunity("failed", assigned=None, state="FAILED"),
    ]

    result = build_officer_performance(staff, opportunities, [], [], now=now)

    assert result["summary"]["staff_total"] == 2
    assert result["summary"]["active_staff"] == 1
    assert result["summary"]["assigned_open"] == 1
    assert result["summary"]["unassigned_open"] == 1
    assert [item["id"] for item in result["unassigned_items"]] == ["open"]
    inactive = next(item for item in result["officers"] if item["user_id"] == "inactive")
    assert inactive["open_assigned"] == 1
    assert inactive["is_active"] is False


def test_performance_output_has_no_composite_score_or_credit_decision_metrics() -> None:
    result = build_officer_performance(
        [{"user_id": "u1", "name": "Officer", "is_active": True}],
        [_opportunity("a", assigned="u1")],
        [],
        [],
        now=datetime(2026, 9, 15, 10, 0),
    )
    text = str(result).lower()

    assert "performance_score" not in text
    assert "approval_rate" not in text
    assert "credit_score" not in text
    assert "loan_amount" not in text
