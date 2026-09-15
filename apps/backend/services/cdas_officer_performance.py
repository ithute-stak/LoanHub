from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Iterable


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _money(value: Any) -> float:
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def _user_id(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _latest_contacts(contacts: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for contact in contacts:
        opportunity_id = str(contact.get("opportunity_id") or "").strip()
        if not opportunity_id:
            continue
        current = latest.get(opportunity_id)
        contacted_at = _as_datetime(contact.get("contacted_at")) or datetime.min
        current_at = _as_datetime(current.get("contacted_at")) if current else None
        if current is None or contacted_at >= (current_at or datetime.min):
            latest[opportunity_id] = contact
    return latest


def _assignment_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id") or ""),
        "client_name": item.get("client_name"),
        "client_reference": item.get("client_reference"),
        "state": str(item.get("state") or "").upper(),
        "pipeline_stage": str(item.get("pipeline_stage") or "identified"),
        "booking_open_date": item.get("booking_open_date"),
        "opportunity_agency_name": item.get("opportunity_agency_name"),
        "opportunity_deduction_amount": round(_money(item.get("opportunity_deduction_amount")), 2),
    }


def build_officer_performance(
    staff: Iterable[dict[str, Any]],
    opportunities: Iterable[dict[str, Any]],
    contacts: Iterable[dict[str, Any]],
    failures: Iterable[dict[str, Any]],
    *,
    now: datetime,
) -> dict[str, Any]:
    """Build transparent operational officer metrics without a composite staff score.

    The workspace describes workload, contact activity, follow-up discipline and recorded
    workflow outcomes. It does not use borrower approval, loan size, credit quality or a
    proprietary ranking to evaluate staff.
    """
    staff_rows = [dict(item) for item in staff]
    opportunity_rows = [dict(item) for item in opportunities]
    contact_rows = [dict(item) for item in contacts]
    failure_rows = [dict(item) for item in failures]

    latest_contact = _latest_contacts(contact_rows)
    cutoff = now - timedelta(days=30)

    contacts_by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for contact in contact_rows:
        user_id = _user_id(contact.get("created_by_user_id"))
        if user_id:
            contacts_by_user[user_id].append(contact)

    failures_by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for failure in failure_rows:
        user_id = _user_id(failure.get("created_by_user_id"))
        if user_id:
            failures_by_user[user_id].append(failure)

    assigned_by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unassigned: list[dict[str, Any]] = []
    for opportunity in opportunity_rows:
        user_id = _user_id(opportunity.get("assigned_to_user_id"))
        state = str(opportunity.get("state") or "").upper()
        if user_id:
            assigned_by_user[user_id].append(opportunity)
        elif state not in {"BOOKED", "FAILED"}:
            unassigned.append(opportunity)

    officer_rows: list[dict[str, Any]] = []
    for staff_item in staff_rows:
        user_id = _user_id(staff_item.get("user_id"))
        if not user_id:
            continue
        assigned = assigned_by_user.get(user_id, [])
        open_items = [item for item in assigned if str(item.get("state") or "").upper() not in {"BOOKED", "FAILED"}]
        booked_items = [item for item in assigned if str(item.get("state") or "").upper() == "BOOKED"]
        failed_items = [item for item in assigned if str(item.get("state") or "").upper() == "FAILED"]

        overdue = 0
        scheduled = 0
        uncontacted = 0
        for item in open_items:
            contact = latest_contact.get(str(item.get("id") or ""))
            if not contact:
                uncontacted += 1
                continue
            follow_up = _as_datetime(contact.get("next_follow_up_at"))
            if follow_up is None:
                continue
            if follow_up < now:
                overdue += 1
            else:
                scheduled += 1

        authored_contacts = contacts_by_user.get(user_id, [])
        recent_contacts = [
            item for item in authored_contacts
            if (_as_datetime(item.get("contacted_at")) or datetime.min) >= cutoff
        ]
        recent_outcomes = Counter(str(item.get("outcome") or "other") for item in recent_contacts)
        recent_channels = Counter(str(item.get("channel") or "other") for item in recent_contacts)
        authored_failures = failures_by_user.get(user_id, [])
        recent_failures = [
            item for item in authored_failures
            if (_as_datetime(item.get("failed_at")) or datetime.min) >= cutoff
        ]

        officer_rows.append(
            {
                "user_id": user_id,
                "name": staff_item.get("name") or "Company staff",
                "email": staff_item.get("email"),
                "phone": staff_item.get("phone"),
                "role": staff_item.get("role"),
                "is_active": bool(staff_item.get("is_active", True)),
                "assigned_total": len(assigned),
                "open_assigned": len(open_items),
                "book_now_assigned": sum(1 for item in open_items if str(item.get("state") or "").upper() == "BOOK_NOW"),
                "upcoming_assigned": sum(1 for item in open_items if str(item.get("state") or "").upper() == "UPCOMING"),
                "open_monthly_deduction_value": round(sum(_money(item.get("opportunity_deduction_amount")) for item in open_items), 2),
                "overdue_follow_ups": overdue,
                "scheduled_follow_ups": scheduled,
                "uncontacted_open": uncontacted,
                "contacts_total": len(authored_contacts),
                "contacts_last_30_days": len(recent_contacts),
                "contact_outcomes_last_30_days": dict(sorted(recent_outcomes.items())),
                "contact_channels_last_30_days": dict(sorted(recent_channels.items())),
                "booked_assigned": len(booked_items),
                "failed_assigned": len(failed_items),
                "booked_by_officer": sum(1 for item in opportunity_rows if _user_id(item.get("booked_by_user_id")) == user_id),
                "failures_reported_last_30_days": len(recent_failures),
            }
        )

    officer_rows.sort(
        key=lambda item: (
            0 if item["is_active"] else 1,
            -int(item["open_assigned"]),
            str(item["name"]).casefold(),
        )
    )
    unassigned.sort(
        key=lambda item: (
            0 if str(item.get("state") or "").upper() == "BOOK_NOW" else 1,
            str(item.get("booking_open_date") or "9999-12-31"),
            str(item.get("client_name") or item.get("client_reference") or "").casefold(),
        )
    )

    all_open = [item for item in opportunity_rows if str(item.get("state") or "").upper() not in {"BOOKED", "FAILED"}]
    total_overdue = 0
    for item in all_open:
        contact = latest_contact.get(str(item.get("id") or ""))
        follow_up = _as_datetime(contact.get("next_follow_up_at")) if contact else None
        if follow_up and follow_up < now:
            total_overdue += 1

    return {
        "as_of": now,
        "window_days": 30,
        "summary": {
            "staff_total": len(officer_rows),
            "active_staff": sum(1 for item in officer_rows if item["is_active"]),
            "assigned_open": sum(1 for item in all_open if _user_id(item.get("assigned_to_user_id"))),
            "unassigned_open": len(unassigned),
            "book_now_open": sum(1 for item in all_open if str(item.get("state") or "").upper() == "BOOK_NOW"),
            "overdue_follow_ups": total_overdue,
            "contacts_last_30_days": sum(
                1 for item in contact_rows if (_as_datetime(item.get("contacted_at")) or datetime.min) >= cutoff
            ),
            "booked_total": sum(1 for item in opportunity_rows if str(item.get("state") or "").upper() == "BOOKED"),
            "failed_total": sum(1 for item in opportunity_rows if str(item.get("state") or "").upper() == "FAILED"),
        },
        "officers": officer_rows,
        "unassigned_items": [_assignment_item(item) for item in unassigned],
    }
