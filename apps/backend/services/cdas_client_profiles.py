from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

from database.models.cdas_booking import CdasAnalysisRecord, CdasBookingOpportunity
from services.cdas_analysis_history import serialize_analysis_record
from services.cdas_booking_monitor import serialize_opportunity


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _snapshot_profile(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    return (snapshot or {}).get("profile") or {}


def _identity_aliases(
    *,
    client_reference: Any = None,
    employee_no: Any = None,
    nid: Any = None,
    client_name: Any = None,
    employer: Any = None,
) -> list[str]:
    aliases: list[str] = []
    for prefix, value in (
        ("reference", client_reference),
        ("employee", employee_no),
        ("nid", nid),
    ):
        normalized = _norm(value)
        if normalized:
            aliases.append(f"{prefix}:{normalized}")

    normalized_name = _norm(client_name)
    normalized_employer = _norm(employer)
    if normalized_name and normalized_employer:
        aliases.append(f"name:{normalized_name}|employer:{normalized_employer}")
    return aliases


def _analysis_aliases(record: CdasAnalysisRecord) -> list[str]:
    profile = _snapshot_profile(record.analysis_snapshot)
    return _identity_aliases(
        client_reference=record.client_reference,
        employee_no=record.employee_no or profile.get("employee_no"),
        nid=record.nid or profile.get("nid"),
        client_name=record.client_name or profile.get("full_name"),
        employer=record.employer or profile.get("employer"),
    )


def _opportunity_aliases(item: CdasBookingOpportunity) -> list[str]:
    profile = _snapshot_profile(item.analysis_snapshot)
    return _identity_aliases(
        client_reference=item.client_reference,
        employee_no=profile.get("employee_no"),
        nid=profile.get("nid"),
        client_name=item.client_name or profile.get("full_name"),
        employer=profile.get("employer"),
    )


def _client_key(primary_alias: str) -> str:
    digest = hashlib.sha256(primary_alias.encode("utf-8")).hexdigest()[:24]
    return f"cdas-client-{digest}"


def _first_nonempty(*values: Any) -> Any:
    for value in values:
        if value is not None and str(value).strip() != "":
            return value
    return None


def _record_sort_key(record: CdasAnalysisRecord) -> tuple[Any, str]:
    return (record.created_at, str(record.id))


def _opportunity_sort_key(item: CdasBookingOpportunity) -> tuple[Any, str]:
    return (item.created_at, str(item.id))


def _merge_groups(groups: dict[str, dict[str, Any]], keep: str, remove: str) -> str:
    if keep == remove:
        return keep
    target = groups[keep]
    source = groups.pop(remove)
    target["analyses"].extend(source["analyses"])
    target["opportunities"].extend(source["opportunities"])
    target["aliases"].update(source["aliases"])
    return keep


def _build_groups(
    analyses: Iterable[CdasAnalysisRecord],
    opportunities: Iterable[CdasBookingOpportunity],
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    alias_to_group: dict[str, str] = {}
    sequence = 0

    def attach(kind: str, entity: Any, aliases: list[str]) -> None:
        nonlocal sequence
        matching = list(dict.fromkeys(alias_to_group[a] for a in aliases if a in alias_to_group))
        if matching:
            group_id = matching[0]
            for other in matching[1:]:
                if other != group_id and other in groups:
                    _merge_groups(groups, group_id, other)
                    for alias, mapped in list(alias_to_group.items()):
                        if mapped == other:
                            alias_to_group[alias] = group_id
        else:
            sequence += 1
            group_id = f"group-{sequence}"
            groups[group_id] = {
                "analyses": [],
                "opportunities": [],
                "aliases": set(),
            }

        group = groups[group_id]
        group[kind].append(entity)
        group["aliases"].update(aliases)
        for alias in aliases:
            alias_to_group[alias] = group_id

    # Analyses are the primary source of truth; opportunities enrich those profiles.
    for record in analyses:
        attach("analyses", record, _analysis_aliases(record))
    for item in opportunities:
        attach("opportunities", item, _opportunity_aliases(item))

    return list(groups.values())


def _profile_payload(group: dict[str, Any], *, include_detail: bool) -> dict[str, Any]:
    analyses: list[CdasAnalysisRecord] = sorted(
        group["analyses"], key=_record_sort_key, reverse=True
    )
    opportunities: list[CdasBookingOpportunity] = sorted(
        group["opportunities"], key=_opportunity_sort_key, reverse=True
    )

    latest = analyses[0] if analyses else None
    latest_opportunity = opportunities[0] if opportunities else None
    latest_snapshot = (
        (latest.analysis_snapshot or {})
        if latest is not None
        else ((latest_opportunity.analysis_snapshot or {}) if latest_opportunity else {})
    )
    profile = _snapshot_profile(latest_snapshot)

    aliases = sorted(group["aliases"])
    fallback_alias = (
        aliases[0]
        if aliases
        else f"analysis:{latest.id}"
        if latest
        else f"opportunity:{latest_opportunity.id}"
        if latest_opportunity
        else "empty"
    )
    primary_alias = next(
        (alias for prefix in ("reference:", "employee:", "nid:") for alias in aliases if alias.startswith(prefix)),
        fallback_alias,
    )

    decision = _first_nonempty(
        getattr(latest, "decision", None),
        latest_snapshot.get("decision"),
    )
    capacity = latest_snapshot.get("capacity") or {}
    booking_term = latest_snapshot.get("booking_term") or {}
    application = latest_snapshot.get("application_context") or {}

    client_name = _first_nonempty(
        getattr(latest, "client_name", None),
        getattr(latest_opportunity, "client_name", None),
        profile.get("full_name"),
    )
    client_reference = _first_nonempty(
        getattr(latest, "client_reference", None),
        getattr(latest_opportunity, "client_reference", None),
        profile.get("employee_no"),
        profile.get("nid"),
    )

    values = {
        "client_key": _client_key(primary_alias),
        "client_name": client_name,
        "client_reference": client_reference,
        "employee_no": _first_nonempty(getattr(latest, "employee_no", None), profile.get("employee_no")),
        "nid": _first_nonempty(getattr(latest, "nid", None), profile.get("nid")),
        "employer": _first_nonempty(getattr(latest, "employer", None), profile.get("employer")),
        "latest_analysis_id": str(latest.id) if latest else None,
        "latest_analyzed_at": latest.created_at.isoformat() if latest and latest.created_at else None,
        "current_agency_code": _first_nonempty(
            getattr(latest, "current_agency_code", None),
            application.get("current_cdas_agency_code"),
            application.get("new_deduction_agency_code"),
        ),
        "current_agency_name": _first_nonempty(
            getattr(latest, "current_agency_name", None),
            application.get("current_cdas_agency_name"),
            application.get("new_deduction_agency_name"),
        ),
        "decision": decision,
        "assessed_available_amount": _first_nonempty(
            getattr(latest, "assessed_available_amount", None),
            capacity.get("assessed_available_amount"),
            capacity.get("max_available_after_selected_deductions"),
            capacity.get("max_available_deduction_amount"),
        ),
        "amount_owing": _first_nonempty(
            getattr(latest, "amount_owing", None), booking_term.get("amount_owing")
        ),
        "booking_months": _first_nonempty(
            getattr(latest, "booking_months", None), booking_term.get("months_required")
        ),
        "next_possible_booking_date": (
            latest.next_possible_booking_date.isoformat()
            if latest and latest.next_possible_booking_date
            else latest_snapshot.get("next_possible_booking_date")
        ),
        "data_quality_issue_count": int(
            _first_nonempty(
                getattr(latest, "data_quality_issue_count", None),
                latest_snapshot.get("data_quality_issue_count"),
                0,
            )
            or 0
        ),
        "analysis_count": len(analyses),
        "opportunity_count": len(opportunities),
        "booked_count": sum(1 for item in opportunities if item.status == "booked"),
        "book_now_count": sum(
            1 for item in opportunities if serialize_opportunity(item).get("state") == "BOOK_NOW"
        ),
        "upcoming_count": sum(
            1 for item in opportunities if serialize_opportunity(item).get("state") == "UPCOMING"
        ),
    }

    if include_detail:
        values.update(
            {
                "profile": profile,
                "current_deductions": latest_snapshot.get("deductions") or [],
                "latest_analysis": serialize_analysis_record(latest) if latest else None,
                "analyses": [serialize_analysis_record(record) for record in analyses],
                "opportunities": [serialize_opportunity(item) for item in opportunities],
            }
        )
    return values


def build_client_profiles(
    analyses: Iterable[CdasAnalysisRecord],
    opportunities: Iterable[CdasBookingOpportunity],
    *,
    include_detail: bool = False,
) -> list[dict[str, Any]]:
    profiles = [
        _profile_payload(group, include_detail=include_detail)
        for group in _build_groups(analyses, opportunities)
    ]
    profiles.sort(
        key=lambda value: value.get("latest_analyzed_at") or "",
        reverse=True,
    )
    return profiles
