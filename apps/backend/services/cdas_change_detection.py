from __future__ import annotations

from typing import Any, Iterable

from database.models.cdas_booking import CdasAnalysisRecord
from services.cdas_client_profiles import _build_groups, build_client_profiles


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _display(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _capacity(snapshot: dict[str, Any]) -> Any:
    values = snapshot.get("capacity") or {}
    for key in (
        "assessed_available_amount",
        "max_available_after_selected_deductions",
        "max_available_deduction_amount",
    ):
        if values.get(key) is not None:
            return values.get(key)
    return None


def _agency(snapshot: dict[str, Any]) -> str | None:
    values = snapshot.get("application_context") or {}
    return (
        values.get("current_cdas_agency_name")
        or values.get("new_deduction_agency_name")
        or None
    )


def _field_values(record: CdasAnalysisRecord) -> dict[str, Any]:
    snapshot = record.analysis_snapshot or {}
    profile = snapshot.get("profile") or {}
    return {
        "decision": record.decision or snapshot.get("decision"),
        "assessed_available_amount": record.assessed_available_amount if record.assessed_available_amount is not None else _capacity(snapshot),
        "next_possible_booking_date": record.next_possible_booking_date or snapshot.get("next_possible_booking_date"),
        "current_agency_name": record.current_agency_name or _agency(snapshot),
        "employer": record.employer or profile.get("employer"),
        "reported_active_monthly_deductions": record.reported_active_monthly_deductions,
        "total_monthly_deductions": record.total_monthly_deductions,
        "own_monthly_deductions": snapshot.get("own_monthly_deductions"),
        "competitor_monthly_deductions": snapshot.get("competitor_monthly_deductions"),
        "data_quality_issue_count": record.data_quality_issue_count,
        "amount_owing": record.amount_owing or (snapshot.get("booking_term") or {}).get("amount_owing"),
        "booking_months": record.booking_months or (snapshot.get("booking_term") or {}).get("months_required"),
    }


FIELD_LABELS = {
    "decision": "CDAS decision",
    "assessed_available_amount": "Available deduction capacity",
    "next_possible_booking_date": "Next booking date",
    "current_agency_name": "Current CDAS agency",
    "employer": "Employer",
    "reported_active_monthly_deductions": "Reported active deductions",
    "total_monthly_deductions": "Booking-valid deductions",
    "own_monthly_deductions": "Our monthly deductions",
    "competitor_monthly_deductions": "Competitor monthly deductions",
    "data_quality_issue_count": "Data-quality issues",
    "amount_owing": "Amount owing",
    "booking_months": "Booking term",
}

MATERIAL_FIELDS = {
    "decision",
    "assessed_available_amount",
    "next_possible_booking_date",
    "current_agency_name",
    "reported_active_monthly_deductions",
    "total_monthly_deductions",
    "own_monthly_deductions",
    "competitor_monthly_deductions",
    "data_quality_issue_count",
}


def _field_changes(previous: CdasAnalysisRecord, latest: CdasAnalysisRecord) -> list[dict[str, Any]]:
    before = _field_values(previous)
    after = _field_values(latest)
    changes: list[dict[str, Any]] = []
    for field, label in FIELD_LABELS.items():
        old = _display(before.get(field))
        new = _display(after.get(field))
        if old == new:
            continue
        changes.append(
            {
                "kind": "FIELD_CHANGED",
                "field": field,
                "label": label,
                "before": old,
                "after": new,
                "impact": "MATERIAL" if field in MATERIAL_FIELDS else "INFO",
            }
        )
    return changes


def _deduction_key(row: dict[str, Any], index: int) -> str:
    reference = _norm(row.get("reference_no"))
    item = _norm(row.get("item_code"))
    agency = _norm(row.get("agency_name"))
    if reference:
        return f"reference:{item}:{reference}" if item else f"reference:{reference}"
    if item or agency:
        return f"item-agency:{item}:{agency}"
    return f"row:{index}:{_norm(row.get('effective_date'))}:{_norm(row.get('deduction_amount'))}"


def _deduction_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "item_code": row.get("item_code"),
        "agency_name": row.get("agency_name"),
        "reference_no": row.get("reference_no"),
        "deduction_amount": row.get("deduction_amount"),
        "status": row.get("status"),
        "effective_date": row.get("effective_date"),
        "expiry_date": row.get("expiry_date"),
        "booking_open_date": row.get("booking_open_date"),
        "data_quality_status": row.get("data_quality_status"),
    }


def _deduction_changes(previous: CdasAnalysisRecord, latest: CdasAnalysisRecord) -> list[dict[str, Any]]:
    previous_rows = (previous.analysis_snapshot or {}).get("deductions") or []
    latest_rows = (latest.analysis_snapshot or {}).get("deductions") or []
    before = {_deduction_key(row, index): row for index, row in enumerate(previous_rows)}
    after = {_deduction_key(row, index): row for index, row in enumerate(latest_rows)}
    changes: list[dict[str, Any]] = []

    for key in sorted(after.keys() - before.keys()):
        changes.append(
            {
                "kind": "DEDUCTION_ADDED",
                "field": "deductions",
                "label": "Deduction added",
                "before": None,
                "after": _deduction_payload(after[key]),
                "impact": "MATERIAL",
            }
        )
    for key in sorted(before.keys() - after.keys()):
        changes.append(
            {
                "kind": "DEDUCTION_REMOVED",
                "field": "deductions",
                "label": "Deduction removed",
                "before": _deduction_payload(before[key]),
                "after": None,
                "impact": "MATERIAL",
            }
        )
    for key in sorted(before.keys() & after.keys()):
        old = _deduction_payload(before[key])
        new = _deduction_payload(after[key])
        if old == new:
            continue
        changed_fields = [field for field in old if old.get(field) != new.get(field)]
        changes.append(
            {
                "kind": "DEDUCTION_MODIFIED",
                "field": "deductions",
                "label": "Deduction changed",
                "before": old,
                "after": new,
                "changed_fields": changed_fields,
                "impact": "MATERIAL",
            }
        )
    return changes


def detect_analysis_changes(
    previous: CdasAnalysisRecord,
    latest: CdasAnalysisRecord,
) -> list[dict[str, Any]]:
    return _field_changes(previous, latest) + _deduction_changes(previous, latest)


def build_change_detection(
    analyses: Iterable[CdasAnalysisRecord],
) -> dict[str, Any]:
    source = list(analyses)
    groups = _build_groups(source, [])
    items: list[dict[str, Any]] = []

    for group in groups:
        records = sorted(
            group["analyses"],
            key=lambda record: (record.created_at, str(record.id)),
            reverse=True,
        )
        if len(records) < 2:
            continue
        latest, previous = records[0], records[1]
        changes = detect_analysis_changes(previous, latest)
        profile = build_client_profiles(records, [], include_detail=False)[0]
        items.append(
            {
                "client_key": profile["client_key"],
                "client_name": profile.get("client_name"),
                "client_reference": profile.get("client_reference"),
                "employer": profile.get("employer"),
                "latest_analysis_id": str(latest.id),
                "previous_analysis_id": str(previous.id),
                "latest_analyzed_at": latest.created_at,
                "previous_analyzed_at": previous.created_at,
                "change_count": len(changes),
                "material_change_count": sum(1 for change in changes if change["impact"] == "MATERIAL"),
                "has_material_changes": any(change["impact"] == "MATERIAL" for change in changes),
                "changes": changes,
            }
        )

    items.sort(key=lambda item: str(item.get("latest_analyzed_at") or ""), reverse=True)
    return {
        "summary": {
            "clients_compared": len(items),
            "clients_with_material_changes": sum(1 for item in items if item["has_material_changes"]),
            "total_changes": sum(item["change_count"] for item in items),
            "material_changes": sum(item["material_change_count"] for item in items),
        },
        "items": items,
        "total": len(items),
    }
