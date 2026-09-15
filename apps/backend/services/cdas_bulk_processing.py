from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


def build_bulk_result_item(
    *,
    index: int,
    client_name: str | None,
    client_reference: str | None,
    analysis: dict[str, Any],
    analysis_id: str,
    archived_new: bool,
) -> dict[str, Any]:
    capacity = analysis.get("capacity") or {}
    assessed = capacity.get("assessed_available_amount")
    if assessed is None:
        assessed = capacity.get("max_available_after_selected_deductions")
    if assessed is None:
        assessed = capacity.get("max_available_deduction_amount")

    profile = analysis.get("profile") or {}
    effective_name = str(client_name or profile.get("full_name") or "").strip() or None
    effective_reference = str(
        client_reference or profile.get("employee_no") or profile.get("nid") or ""
    ).strip() or None

    return {
        "index": index,
        "status": "SUCCESS",
        "client_name": effective_name,
        "client_reference": effective_reference,
        "analysis_id": analysis_id,
        "archived_new": bool(archived_new),
        "decision": str(analysis.get("decision") or "REVIEW_REQUIRED"),
        "next_possible_booking_date": analysis.get("next_possible_booking_date"),
        "assessed_available_amount": float(assessed) if assessed is not None else None,
        "data_quality_issue_count": int(analysis.get("data_quality_issue_count") or 0),
        "error": None,
    }


def build_bulk_error_item(
    *,
    index: int,
    client_name: str | None,
    client_reference: str | None,
    error: str,
) -> dict[str, Any]:
    return {
        "index": index,
        "status": "ERROR",
        "client_name": (client_name or "").strip() or None,
        "client_reference": (client_reference or "").strip() or None,
        "analysis_id": None,
        "archived_new": False,
        "decision": None,
        "next_possible_booking_date": None,
        "assessed_available_amount": None,
        "data_quality_issue_count": 0,
        "error": str(error or "CDAS analysis failed").strip(),
    }


def build_bulk_summary(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    values = list(items)
    successful = [item for item in values if item.get("status") == "SUCCESS"]
    failed = [item for item in values if item.get("status") == "ERROR"]
    decisions = Counter(str(item.get("decision")) for item in successful if item.get("decision"))
    return {
        "total": len(values),
        "successful": len(successful),
        "errors": len(failed),
        "archived_new": sum(1 for item in successful if item.get("archived_new")),
        "archive_reused": sum(1 for item in successful if not item.get("archived_new")),
        "review_required": decisions.get("REVIEW_REQUIRED", 0),
        "decisions": dict(sorted(decisions.items())),
    }
