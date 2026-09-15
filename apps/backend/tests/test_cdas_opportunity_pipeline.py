from __future__ import annotations

from uuid import uuid4

import pytest

from database.models.cdas_booking import CdasBookingOpportunity
from services.cdas_opportunity_pipeline import (
    PIPELINE_STAGES,
    build_opportunity_pipeline,
    transition_pipeline_stage,
)


class FakeDb:
    def __init__(self):
        self.commits = 0
        self.refreshed = []

    def commit(self):
        self.commits += 1

    def refresh(self, item):
        self.refreshed.append(item)


def opportunity(*, id_value: str, stage: str, amount: float, status: str = "monitoring") -> dict:
    return {
        "id": id_value,
        "client_name": f"Client {id_value}",
        "client_reference": id_value,
        "status": status,
        "state": "BOOKED" if status == "booked" else "FAILED" if stage == "failed" else "UPCOMING",
        "pipeline_stage": stage,
        "booking_open_date": "2026-10-01",
        "opportunity_deduction_amount": amount,
    }


def test_pipeline_exposes_all_eight_business_stages_in_order():
    assert [stage for stage, _ in PIPELINE_STAGES] == [
        "identified",
        "contact_client",
        "documents_required",
        "ready_to_book",
        "booking_submitted",
        "approved",
        "failed",
        "booked",
    ]


def test_pipeline_summary_separates_active_failed_and_booked_value():
    board = build_opportunity_pipeline([
        opportunity(id_value="a", stage="identified", amount=100),
        opportunity(id_value="b", stage="ready_to_book", amount=200),
        opportunity(id_value="c", stage="failed", amount=300),
        opportunity(id_value="d", stage="identified", amount=400, status="booked"),
    ])

    assert board["total"] == 4
    assert board["summary"] == {
        "active": 2,
        "failed": 1,
        "booked": 1,
        "active_monthly_deduction_value": 300.0,
        "failed_monthly_deduction_value": 300.0,
        "booked_monthly_deduction_value": 400.0,
    }
    assert next(stage for stage in board["stages"] if stage["id"] == "booked")["count"] == 1


def test_booked_pipeline_stage_is_terminal():
    item = CdasBookingOpportunity(
        status="booked",
        pipeline_stage="booked",
    )
    with pytest.raises(ValueError, match="terminal"):
        transition_pipeline_stage(
            FakeDb(),
            item=item,
            target_stage="approved",
            user_id=uuid4(),
        )


def test_marking_pipeline_booked_synchronizes_legacy_booking_fields():
    user_id = uuid4()
    item = CdasBookingOpportunity(
        status="monitoring",
        pipeline_stage="approved",
    )
    db = FakeDb()

    transition_pipeline_stage(
        db,
        item=item,
        target_stage="booked",
        user_id=user_id,
        allow_direct_booked=True,
    )

    assert item.pipeline_stage == "booked"
    assert item.status == "booked"
    assert item.booked_at is not None
    assert item.booked_by_user_id == user_id
    assert item.pipeline_updated_at is not None
    assert item.pipeline_updated_by_user_id == user_id
    assert db.commits == 1


def test_unknown_pipeline_stage_is_rejected():
    item = CdasBookingOpportunity(status="monitoring", pipeline_stage="identified")
    with pytest.raises(ValueError, match="Unsupported"):
        transition_pipeline_stage(
            FakeDb(),
            item=item,
            target_stage="somewhere_else",
            user_id=uuid4(),
        )
