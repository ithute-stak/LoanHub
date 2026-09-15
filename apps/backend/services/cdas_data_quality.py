from __future__ import annotations

from typing import Any, Iterable


SEVERITY_ORDER = {"BLOCKER": 0, "WARNING": 1, "INFO": 2}


def _money(value: Any) -> float:
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def _deduction_context(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "item_code": row.get("item_code"),
        "agency_name": row.get("agency_name"),
        "reference_no": row.get("reference_no"),
        "deduction_amount": _money(row.get("deduction_amount")),
        "effective_date": row.get("effective_date"),
        "expiry_date": row.get("expiry_date"),
        "status": row.get("status"),
        "data_quality_status": row.get("data_quality_status"),
    }


def _issue(
    category: str,
    severity: str,
    label: str,
    message: str,
    *,
    source: str,
    deduction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "category": category,
        "severity": severity,
        "label": label,
        "message": message,
        "source": source,
        "deduction": _deduction_context(deduction) if deduction else None,
    }


def inspect_profile_quality(profile: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    if str(profile.get("decision") or "").upper() == "REVIEW_REQUIRED":
        issues.append(_issue(
            "REVIEW_REQUIRED",
            "BLOCKER",
            "Analysis requires review",
            "The latest CDAS analysis is REVIEW REQUIRED, so its booking timing must be verified before staff rely on it.",
            source="ANALYSIS",
        ))

    if not profile.get("client_name"):
        issues.append(_issue(
            "MISSING_CLIENT_NAME",
            "WARNING",
            "Client name missing",
            "The latest client profile has no usable client name.",
            source="PROFILE",
        ))

    if not any(profile.get(key) for key in ("client_reference", "employee_no", "nid")):
        issues.append(_issue(
            "MISSING_STRONG_IDENTIFIER",
            "WARNING",
            "Strong client identifier missing",
            "No client reference, employee number or NID is available. Future analyses can only be matched conservatively using name plus employer when both exist.",
            source="PROFILE",
        ))

    if not profile.get("employer"):
        issues.append(_issue(
            "MISSING_EMPLOYER",
            "WARNING",
            "Employer missing",
            "The latest CDAS profile does not contain an employer.",
            source="PROFILE",
        ))

    if not profile.get("current_agency_name") and not profile.get("current_agency_code"):
        issues.append(_issue(
            "MISSING_CDAS_AGENCY",
            "WARNING",
            "Current CDAS agency missing",
            "LoanHub could not identify the current CDAS agency from the latest analysis.",
            source="ANALYSIS",
        ))

    if profile.get("assessed_available_amount") is None:
        issues.append(_issue(
            "CAPACITY_UNKNOWN",
            "WARNING",
            "Available deduction capacity unknown",
            "The latest analysis does not contain a usable assessed Max Available Deduction Amount.",
            source="ANALYSIS",
        ))

    for row in profile.get("current_deductions") or []:
        quality = str(row.get("data_quality_status") or "OK").upper()
        reported_active = bool(row.get("reported_active"))
        excluded = bool(row.get("excluded_from_booking"))

        if quality == "MISSING_EXPIRY":
            issues.append(_issue(
                "MISSING_EXPIRY",
                "BLOCKER",
                "Active deduction expiry missing",
                row.get("data_quality_message") or "An Active deduction has no expiry month and is excluded from booking-window calculations.",
                source="DEDUCTION",
                deduction=row,
            ))
        elif quality == "DATE_CONFLICT":
            issues.append(_issue(
                "DATE_CONFLICT",
                "BLOCKER",
                "Deduction dates conflict",
                row.get("data_quality_message") or "A deduction has contradictory effective and expiry dates and is excluded from booking calculations.",
                source="DEDUCTION",
                deduction=row,
            ))
        elif quality != "OK":
            issues.append(_issue(
                "DEDUCTION_DATA_ISSUE",
                "BLOCKER",
                "Deduction data requires review",
                row.get("data_quality_message") or f"The deduction is marked with data-quality status {quality}.",
                source="DEDUCTION",
                deduction=row,
            ))

        if reported_active and excluded and quality == "OK":
            issues.append(_issue(
                "ACTIVE_DEDUCTION_EXCLUDED",
                "BLOCKER",
                "Active deduction excluded unexpectedly",
                "An Active deduction is excluded from booking calculations even though its quality status is OK.",
                source="DEDUCTION",
                deduction=row,
            ))

        if reported_active and not str(row.get("reference_no") or "").strip():
            issues.append(_issue(
                "MISSING_DEDUCTION_REFERENCE",
                "WARNING",
                "Active deduction reference missing",
                "This Active deduction has no reference number, which can make later matching and reconciliation less reliable.",
                source="DEDUCTION",
                deduction=row,
            ))

        if reported_active and _money(row.get("deduction_amount")) <= 0:
            issues.append(_issue(
                "INVALID_DEDUCTION_AMOUNT",
                "WARNING",
                "Active deduction amount is zero or invalid",
                "This Active deduction does not contain a positive monthly deduction amount.",
                source="DEDUCTION",
                deduction=row,
            ))

    issues.sort(key=lambda value: (SEVERITY_ORDER.get(value["severity"], 9), value["category"]))
    return issues


def _quality_score(issues: list[dict[str, Any]]) -> int:
    penalty = sum(
        25 if issue["severity"] == "BLOCKER" else 10 if issue["severity"] == "WARNING" else 3
        for issue in issues
    )
    return max(0, 100 - penalty)


def build_data_quality_centre(profiles: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    category_counts: dict[str, dict[str, Any]] = {}

    for source in profiles:
        profile = dict(source)
        issues = inspect_profile_quality(profile)
        blocker_count = sum(1 for issue in issues if issue["severity"] == "BLOCKER")
        warning_count = sum(1 for issue in issues if issue["severity"] == "WARNING")
        excluded_amount = round(sum(
            float((issue.get("deduction") or {}).get("deduction_amount") or 0)
            for issue in issues
            if issue["severity"] == "BLOCKER" and issue.get("deduction")
        ), 2)

        for issue in issues:
            aggregate = category_counts.setdefault(
                issue["category"],
                {
                    "category": issue["category"],
                    "label": issue["label"],
                    "severity": issue["severity"],
                    "count": 0,
                },
            )
            aggregate["count"] += 1

        items.append({
            "client_key": profile.get("client_key"),
            "client_name": profile.get("client_name"),
            "client_reference": profile.get("client_reference"),
            "employee_no": profile.get("employee_no"),
            "nid": profile.get("nid"),
            "employer": profile.get("employer"),
            "current_agency_name": profile.get("current_agency_name"),
            "decision": profile.get("decision"),
            "latest_analysis_id": profile.get("latest_analysis_id"),
            "latest_analyzed_at": profile.get("latest_analyzed_at"),
            "quality_score": _quality_score(issues),
            "issue_count": len(issues),
            "blocker_count": blocker_count,
            "warning_count": warning_count,
            "excluded_monthly_amount": excluded_amount,
            "issues": issues,
        })

    items.sort(key=lambda value: (
        0 if value["blocker_count"] else 1 if value["warning_count"] else 2,
        int(value["quality_score"]),
        str(value.get("client_name") or value.get("client_reference") or "").casefold(),
    ))
    categories = sorted(
        category_counts.values(),
        key=lambda value: (SEVERITY_ORDER.get(value["severity"], 9), -int(value["count"]), value["label"]),
    )
    clients_with_issues = [item for item in items if item["issue_count"]]

    return {
        "summary": {
            "clients_checked": len(items),
            "clients_with_issues": len(clients_with_issues),
            "blocker_clients": sum(1 for item in items if item["blocker_count"]),
            "total_issues": sum(item["issue_count"] for item in items),
            "blocker_issues": sum(item["blocker_count"] for item in items),
            "warning_issues": sum(item["warning_count"] for item in items),
            "excluded_monthly_amount": round(sum(item["excluded_monthly_amount"] for item in items), 2),
        },
        "categories": categories,
        "items": items,
        "total": len(items),
    }
