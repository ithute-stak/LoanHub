from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from database.models.cdas_booking import CdasOpportunityContact
from services.cdas_contact_followups import (
    build_follow_up_workspace,
    normalize_channel,
    normalize_outcome,
)


def contact(opportunity_id, *, when, next_at, outcome="call_back"):
    return CdasOpportunityContact(
        id=uuid4(),
        company_id=uuid4(),
        opportunity_id=opportunity_id,
        channel="call",
        outcome=outcome,
        notes="Follow up note",
        contacted_at=when,
        next_follow_up_at=next_at,
        created_by_user_id=uuid4(),
        created_at=when,
    )


def test_contact_channels_and_outcomes_are_strict():
    assert normalize_channel("WhatsApp") == "whatsapp"
    assert normalize_outcome("documents_received") == "documents_received"
    with pytest.raises(ValueError, match="channel"):
        normalize_channel("telegram")
    with pytest.raises(ValueError, match="outcome"):
        normalize_outcome("maybe")


def test_latest_contact_supersedes_old_follow_up_schedule():
    opportunity_id = uuid4()
    now = datetime(2026, 9, 15, 9, 0)
    old = contact(
        opportunity_id,
        when=now - timedelta(days=5),
        next_at=now - timedelta(days=2),
    )
    latest = contact(
        opportunity_id,
        when=now - timedelta(hours=1),
        next_at=now + timedelta(days=2),
    )
    workspace = build_follow_up_workspace(
        [{
            "id": str(opportunity_id),
            "client_name": "Test Client",
            "state": "UPCOMING",
            "assigned_to_user_id": None,
            "opportunity_deduction_amount": 1000,
        }],
        [old, latest],
        now=now,
    )
    item = workspace["items"][0]
    assert item["contact_count"] == 2
    assert item["next_follow_up_at"] == latest.next_follow_up_at
    assert item["is_follow_up_overdue"] is False
    assert workspace["summary"]["scheduled_follow_ups"] == 1
    assert workspace["summary"]["overdue_follow_ups"] == 0


def test_follow_up_summary_counts_only_open_work_for_management_metrics():
    now = datetime(2026, 9, 15, 9, 0)
    workspace = build_follow_up_workspace(
        [
            {"id": "1", "state": "UPCOMING", "assigned_to_user_id": None},
            {"id": "2", "state": "BOOK_NOW", "assigned_to_user_id": str(uuid4())},
            {"id": "3", "state": "FAILED", "assigned_to_user_id": None},
            {"id": "4", "state": "BOOKED", "assigned_to_user_id": None},
        ],
        [],
        now=now,
    )
    assert workspace["summary"]["open"] == 2
    assert workspace["summary"]["unassigned"] == 1
    assert workspace["summary"]["contacted"] == 0
