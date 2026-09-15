from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from sqlalchemy.orm import Session

from database.models.cdas_booking import CdasBookingOpportunity


PIPELINE_STAGES: tuple[tuple[str, str], ...] = (
    ("identified", "Identified"),
    ("contact_client", "Contact Client"),
    ("documents_required", "Documents Required"),
    ("ready_to_book", "Ready to Book"),
    ("booking_submitted", "Booking Submitted"),
    ("approved", "Approved"),
    ("failed", "Failed"),
    ("booked", "Booked"),
)
PIPELINE_STAGE_IDS = {stage for stage, _ in PIPELINE_STAGES}
PIPELINE_LABELS = dict(PIPELINE_STAGES)


def normalize_pipeline_stage(value: Any) -> str:
    stage = str(value or "identified").strip().lower()
    return stage if stage in PIPELINE_STAGE_IDS else "identified"


def pipeline_stage_for_item(item: CdasBookingOpportunity) -> str:
    if item.status == "booked":
        return "booked"
    return normalize_pipeline_stage(item.pipeline_stage)


def transition_pipeline_stage(
    db: Session,
    *,
    item: CdasBookingOpportunity,
    target_stage: str,
    user_id,
    allow_direct_booked: bool = False,
) -> CdasBookingOpportunity:
    target = str(target_stage or "").strip().lower()
    if target not in PIPELINE_STAGE_IDS:
        raise ValueError("Unsupported CDAS pipeline stage")

    current = pipeline_stage_for_item(item)
    if current == "booked" and target != "booked":
        raise ValueError("Booked CDAS opportunities are terminal and cannot be moved back")
    if target == "booked" and current != "booked" and not allow_direct_booked and current != "approved":
        raise ValueError("Move the opportunity to Approved before marking the pipeline stage Booked")

    if current == target:
        return item

    now = datetime.utcnow()
    item.pipeline_stage = target
    item.pipeline_updated_at = now
    item.pipeline_updated_by_user_id = user_id

    if target == "booked":
        item.status = "booked"
        item.booked_at = item.booked_at or now
        item.booked_by_user_id = item.booked_by_user_id or user_id

    db.commit()
    db.refresh(item)
    return item


def build_opportunity_pipeline(opportunities: Iterable[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {stage: [] for stage, _ in PIPELINE_STAGES}

    for source in opportunities:
        item = dict(source)
        stage = normalize_pipeline_stage(item.get("pipeline_stage"))
        if str(item.get("status") or "").lower() == "booked":
            stage = "booked"
        item["pipeline_stage"] = stage
        grouped[stage].append(item)

    def sort_key(item: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(item.get("booking_open_date") or "9999-12-31"),
            str(item.get("client_name") or item.get("client_reference") or "").casefold(),
            str(item.get("id") or ""),
        )

    stage_payloads: list[dict[str, Any]] = []
    for order, (stage, label) in enumerate(PIPELINE_STAGES):
        items = sorted(grouped[stage], key=sort_key)
        stage_payloads.append(
            {
                "id": stage,
                "label": label,
                "order": order,
                "count": len(items),
                "monthly_deduction_value": round(
                    sum(float(item.get("opportunity_deduction_amount") or 0) for item in items),
                    2,
                ),
                "items": items,
            }
        )

    active_stage_ids = {
        "identified",
        "contact_client",
        "documents_required",
        "ready_to_book",
        "booking_submitted",
        "approved",
    }
    active_items = [
        item
        for stage in stage_payloads
        if stage["id"] in active_stage_ids
        for item in stage["items"]
    ]
    failed_items = grouped["failed"]
    booked_items = grouped["booked"]

    return {
        "stages": stage_payloads,
        "summary": {
            "active": len(active_items),
            "failed": len(failed_items),
            "booked": len(booked_items),
            "active_monthly_deduction_value": round(
                sum(float(item.get("opportunity_deduction_amount") or 0) for item in active_items),
                2,
            ),
            "failed_monthly_deduction_value": round(
                sum(float(item.get("opportunity_deduction_amount") or 0) for item in failed_items),
                2,
            ),
            "booked_monthly_deduction_value": round(
                sum(float(item.get("opportunity_deduction_amount") or 0) for item in booked_items),
                2,
            ),
        },
        "total": sum(stage["count"] for stage in stage_payloads),
    }
