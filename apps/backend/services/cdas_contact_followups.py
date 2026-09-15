from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Iterable

from database.models.cdas_booking import CdasOpportunityContact

CONTACT_CHANNELS = ("call", "whatsapp", "sms", "email", "other")
CONTACT_OUTCOMES = (
    "no_answer",
    "interested",
    "not_interested",
    "call_back",
    "documents_requested",
    "documents_received",
    "submitted",
    "other",
)


def normalize_channel(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in CONTACT_CHANNELS:
        raise ValueError("Unsupported contact channel")
    return normalized


def normalize_outcome(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in CONTACT_OUTCOMES:
        raise ValueError("Unsupported contact outcome")
    return normalized


def serialize_contact(row: CdasOpportunityContact) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "opportunity_id": str(row.opportunity_id),
        "channel": row.channel,
        "outcome": row.outcome,
        "notes": row.notes,
        "contacted_at": row.contacted_at,
        "next_follow_up_at": row.next_follow_up_at,
        "created_by_user_id": str(row.created_by_user_id) if row.created_by_user_id else None,
        "created_at": row.created_at,
    }


def build_follow_up_workspace(
    opportunities: Iterable[dict[str, Any]],
    contacts: Iterable[CdasOpportunityContact],
    *,
    now: datetime,
) -> dict[str, Any]:
    by_opportunity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in contacts:
        by_opportunity[str(row.opportunity_id)].append(serialize_contact(row))

    items: list[dict[str, Any]] = []
    for source in opportunities:
        item = dict(source)
        history = sorted(
            by_opportunity.get(str(item.get("id") or ""), []),
            key=lambda value: str(value.get("contacted_at") or ""),
            reverse=True,
        )
        latest = history[0] if history else None
        # A newer contact supersedes the previous follow-up instruction. This
        # prevents an old missed date from staying overdue after staff make a
        # newer contact and intentionally set a different next action.
        next_follow_up = latest.get("next_follow_up_at") if latest else None
        item.update(
            {
                "contact_count": len(history),
                "latest_contact": latest,
                "next_follow_up_at": next_follow_up,
                "is_follow_up_overdue": bool(next_follow_up and next_follow_up < now),
                "contacts": history,
            }
        )
        items.append(item)

    items.sort(
        key=lambda item: (
            0 if item.get("is_follow_up_overdue") else 1,
            str(item.get("next_follow_up_at") or "9999-12-31"),
            str(item.get("client_name") or item.get("client_reference") or "").casefold(),
        )
    )

    open_items = [item for item in items if str(item.get("state") or "").upper() not in {"BOOKED", "FAILED"}]
    return {
        "as_of": now,
        "summary": {
            "open": len(open_items),
            "unassigned": sum(1 for item in open_items if not item.get("assigned_to_user_id")),
            "overdue_follow_ups": sum(1 for item in open_items if item.get("is_follow_up_overdue")),
            "scheduled_follow_ups": sum(1 for item in open_items if item.get("next_follow_up_at")),
            "contacted": sum(1 for item in open_items if item.get("contact_count", 0) > 0),
        },
        "items": items,
        "total": len(items),
    }
