from __future__ import annotations

import hashlib
import re
from itertools import combinations
from typing import Any, Iterable


CONFIDENCE_ORDER = {"HIGH": 0, "MEDIUM": 1}


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def _strong_identifiers(profile: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for key in ("client_reference", "employee_no", "nid"):
        normalized = _norm(profile.get(key))
        if normalized:
            values[key] = normalized
    return values


def _candidate_id(left_key: str, right_key: str) -> str:
    joined = "|".join(sorted((left_key, right_key)))
    return f"cdas-duplicate-{hashlib.sha256(joined.encode('utf-8')).hexdigest()[:20]}"


def _profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "client_key": profile.get("client_key"),
        "client_name": profile.get("client_name"),
        "client_reference": profile.get("client_reference"),
        "employee_no": profile.get("employee_no"),
        "nid": profile.get("nid"),
        "employer": profile.get("employer"),
        "current_agency_name": profile.get("current_agency_name"),
        "latest_analysis_id": profile.get("latest_analysis_id"),
        "latest_analyzed_at": profile.get("latest_analyzed_at"),
        "analysis_count": int(profile.get("analysis_count") or 0),
        "opportunity_count": int(profile.get("opportunity_count") or 0),
    }


def _evaluate_pair(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any] | None:
    left_key = str(left.get("client_key") or "").strip()
    right_key = str(right.get("client_key") or "").strip()
    if not left_key or not right_key or left_key == right_key:
        return None

    left_ids = _strong_identifiers(left)
    right_ids = _strong_identifiers(right)
    shared_ids: list[dict[str, str]] = []
    for left_field, left_value in left_ids.items():
        for right_field, right_value in right_ids.items():
            if left_value == right_value:
                shared_ids.append(
                    {
                        "value": left_value,
                        "left_field": left_field,
                        "right_field": right_field,
                    }
                )

    left_name = _norm(left.get("client_name"))
    right_name = _norm(right.get("client_name"))
    same_name = bool(left_name and left_name == right_name)
    left_employer = _norm(left.get("employer"))
    right_employer = _norm(right.get("employer"))
    same_employer = bool(left_employer and left_employer == right_employer)

    reasons: list[str] = []
    evidence: list[str] = []
    confidence: str | None = None

    if shared_ids:
        confidence = "HIGH"
        reasons.append("SHARED_STRONG_IDENTIFIER")
        fields = sorted({item["left_field"] for item in shared_ids} | {item["right_field"] for item in shared_ids})
        evidence.append(f"Exact shared identifier across: {', '.join(fields)}")

    if same_name and same_employer:
        confidence = "HIGH"
        reasons.append("SAME_NAME_AND_EMPLOYER")
        evidence.append("Exact normalized client name and employer match")

    if confidence is None and same_name:
        employer_incomplete = not left_employer or not right_employer
        identifier_incomplete = not left_ids or not right_ids
        if employer_incomplete and identifier_incomplete:
            confidence = "MEDIUM"
            reasons.append("SAME_NAME_INCOMPLETE_IDENTITY")
            evidence.append("Exact normalized client name match with incomplete employer/identifier data")

    if confidence is None:
        return None

    return {
        "candidate_id": _candidate_id(left_key, right_key),
        "confidence": confidence,
        "reason_codes": reasons,
        "evidence": evidence,
        "shared_identifiers": shared_ids,
        "left": _profile_summary(left),
        "right": _profile_summary(right),
    }


def build_duplicate_detection(profiles: Iterable[dict[str, Any]]) -> dict[str, Any]:
    values = [dict(profile) for profile in profiles]
    candidates: list[dict[str, Any]] = []
    affected_clients: set[str] = set()

    for left, right in combinations(values, 2):
        candidate = _evaluate_pair(left, right)
        if not candidate:
            continue
        candidates.append(candidate)
        affected_clients.add(str(candidate["left"]["client_key"]))
        affected_clients.add(str(candidate["right"]["client_key"]))

    candidates.sort(
        key=lambda item: (
            CONFIDENCE_ORDER.get(str(item["confidence"]), 9),
            str(item["left"].get("client_name") or "").casefold(),
            str(item["right"].get("client_name") or "").casefold(),
            str(item["candidate_id"]),
        )
    )

    return {
        "summary": {
            "profiles_checked": len(values),
            "candidate_pairs": len(candidates),
            "high_confidence_pairs": sum(1 for item in candidates if item["confidence"] == "HIGH"),
            "medium_confidence_pairs": sum(1 for item in candidates if item["confidence"] == "MEDIUM"),
            "affected_client_profiles": len(affected_clients),
        },
        "items": candidates,
        "total": len(candidates),
        "policy": {
            "automatic_merge": False,
            "fuzzy_name_matching": False,
            "description": "Review-only duplicate detection based on exact identity evidence. LoanHub does not merge client profiles automatically.",
        },
    }
