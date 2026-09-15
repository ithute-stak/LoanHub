from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _contains(value: Any, needle: str | None) -> bool:
    wanted = _text(needle)
    return not wanted or wanted in _text(value)


def _matches_query(item: dict[str, Any], query: str | None, fields: Iterable[str]) -> bool:
    needle = _text(query)
    if not needle:
        return True
    return any(needle in _text(item.get(field)) for field in fields)


def _matches_date_range(value: Any, start: date | None, end: date | None) -> bool:
    if start is None and end is None:
        return True
    current = _date(value)
    if current is None:
        return False
    if start is not None and current < start:
        return False
    if end is not None and current > end:
        return False
    return True


def _matches_number_range(value: Any, minimum: float | None, maximum: float | None) -> bool:
    if minimum is None and maximum is None:
        return True
    current = _number(value)
    if current is None:
        return False
    if minimum is not None and current < minimum:
        return False
    if maximum is not None and current > maximum:
        return False
    return True


def _matches_quality(item: dict[str, Any], quality: str | None) -> bool:
    wanted = _text(quality)
    if not wanted or wanted == "all":
        return True
    issue_count = int(item.get("data_quality_issue_count") or 0)
    if wanted == "issues":
        return issue_count > 0
    if wanted == "clean":
        return issue_count == 0
    return True


def enrich_opportunity(item: dict[str, Any], *, assigned_name: str | None = None) -> dict[str, Any]:
    result = dict(item)
    snapshot = item.get("analysis_snapshot") or {}
    profile = snapshot.get("profile") or {}
    capacity = snapshot.get("capacity") or {}
    assessed = capacity.get("assessed_available_amount")
    if assessed is None:
        assessed = capacity.get("max_available_after_selected_deductions")
    if assessed is None:
        assessed = capacity.get("max_available_deduction_amount")
    result.update(
        {
            "employer": profile.get("employer"),
            "decision": snapshot.get("decision"),
            "assessed_available_amount": _number(assessed),
            "data_quality_issue_count": int(snapshot.get("data_quality_issue_count") or 0),
            "assigned_to_name": assigned_name,
        }
    )
    return result


def filter_analyses(
    items: Iterable[dict[str, Any]],
    *,
    query: str | None = None,
    employer: str | None = None,
    agency: str | None = None,
    decision: str | None = None,
    quality: str | None = None,
    booking_from: date | None = None,
    booking_to: date | None = None,
    analyzed_from: date | None = None,
    analyzed_to: date | None = None,
    min_capacity: float | None = None,
    max_capacity: float | None = None,
) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for item in items:
        if not _matches_query(
            item,
            query,
            ("client_name", "client_reference", "employee_no", "nid", "employer", "current_agency_code", "current_agency_name"),
        ):
            continue
        if not _contains(item.get("employer"), employer):
            continue
        if not _contains(item.get("current_agency_name"), agency):
            continue
        if decision and _text(item.get("decision")) != _text(decision):
            continue
        if not _matches_quality(item, quality):
            continue
        if not _matches_date_range(item.get("next_possible_booking_date"), booking_from, booking_to):
            continue
        if not _matches_date_range(item.get("analyzed_at"), analyzed_from, analyzed_to):
            continue
        if not _matches_number_range(item.get("assessed_available_amount"), min_capacity, max_capacity):
            continue
        values.append(dict(item))
    return values


def filter_opportunities(
    items: Iterable[dict[str, Any]],
    *,
    query: str | None = None,
    employer: str | None = None,
    agency: str | None = None,
    decision: str | None = None,
    state: str | None = None,
    pipeline_stage: str | None = None,
    assigned_to_user_id: str | None = None,
    quality: str | None = None,
    booking_from: date | None = None,
    booking_to: date | None = None,
    min_capacity: float | None = None,
    max_capacity: float | None = None,
    min_deduction: float | None = None,
    max_deduction: float | None = None,
) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for source in items:
        item = dict(source)
        if not _matches_query(
            item,
            query,
            (
                "client_name",
                "client_reference",
                "employer",
                "opportunity_agency_name",
                "opportunity_item_code",
                "opportunity_reference_no",
                "assigned_to_name",
            ),
        ):
            continue
        if not _contains(item.get("employer"), employer):
            continue
        if not _contains(item.get("opportunity_agency_name"), agency):
            continue
        if decision and _text(item.get("decision")) != _text(decision):
            continue
        if state and _text(item.get("state")) != _text(state):
            continue
        if pipeline_stage and _text(item.get("pipeline_stage")) != _text(pipeline_stage):
            continue
        if assigned_to_user_id:
            actual = str(item.get("assigned_to_user_id") or "")
            if assigned_to_user_id == "unassigned":
                if actual:
                    continue
            elif actual != assigned_to_user_id:
                continue
        if not _matches_quality(item, quality):
            continue
        if not _matches_date_range(item.get("booking_open_date"), booking_from, booking_to):
            continue
        if not _matches_number_range(item.get("assessed_available_amount"), min_capacity, max_capacity):
            continue
        if not _matches_number_range(item.get("opportunity_deduction_amount"), min_deduction, max_deduction):
            continue
        values.append(item)
    return values


def build_search_options(
    analyses: Iterable[dict[str, Any]],
    opportunities: Iterable[dict[str, Any]],
    officers: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    analysis_values = list(analyses)
    opportunity_values = list(opportunities)

    def unique(values: Iterable[Any]) -> list[str]:
        selected = {str(value).strip() for value in values if str(value or "").strip()}
        return sorted(selected, key=str.lower)

    return {
        "employers": unique([item.get("employer") for item in analysis_values] + [item.get("employer") for item in opportunity_values]),
        "agencies": unique([item.get("current_agency_name") for item in analysis_values] + [item.get("opportunity_agency_name") for item in opportunity_values]),
        "decisions": unique([item.get("decision") for item in analysis_values] + [item.get("decision") for item in opportunity_values]),
        "states": unique(item.get("state") for item in opportunity_values),
        "pipeline_stages": unique(item.get("pipeline_stage") for item in opportunity_values),
        "officers": list(officers),
    }
