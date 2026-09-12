from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Any

import httpx


PROVIDER = "lelefa_debt_collectors"
INTEGRATION_TYPE = "managed_collections"
RECORD_MODULE = "collections"
RECORD_TYPE = "lelefa_referral"
IDEMPOTENCY_HEADER = "X-Idempotency-Key"
BRIDGE_TOKEN_HEADER = "X-Ithute-Bridge-Token"
LELEFA_API_BASE_URL = "https://api.lelefadebtcollectors.co.ls"
LOANHUB_API_BASE_URL = "https://api.loanhub.co.ls/api/v1"
INTEGRATION_TIMEOUT_SECONDS = 15.0

DEFAULT_RULES: dict[str, Any] = {
    "min_days_past_due": 120,
    "min_overdue_amount": 0,
    "min_outstanding_balance": 0,
    "stages": [],
    "priorities": [],
    "exclude_active_promises": True,
    "exclude_legal_handover": False,
    "share_national_id": False,
    "share_employment": False,
}


def integration_base_url() -> str:
    """Lelefa is an Ithute-owned platform with a fixed production API address."""
    return LELEFA_API_BASE_URL


def integration_timeout_seconds() -> float:
    return INTEGRATION_TIMEOUT_SECONDS


def new_bridge_token() -> str:
    """Create a referral-scoped capability token automatically.

    There is deliberately no operator-managed shared integration secret. The token is
    unique to one referral, is never returned to the company UI, and is verified
    against LoanHub before Lelefa accepts the referral.
    """
    return secrets.token_urlsafe(32)


def bridge_token_matches(stored: str | None, received: str | None) -> bool:
    if not stored or not received:
        return False
    return secrets.compare_digest(str(stored), str(received))


def normalize_rules(configuration: dict | None) -> dict[str, Any]:
    raw = dict(configuration or {})
    rules = dict(DEFAULT_RULES)
    stored = raw.get("rules") if isinstance(raw.get("rules"), dict) else raw
    for key in rules:
        if key in stored:
            rules[key] = stored[key]
    rules["min_days_past_due"] = max(1, int(rules["min_days_past_due"] or 120))
    rules["min_overdue_amount"] = max(0, float(rules["min_overdue_amount"] or 0))
    rules["min_outstanding_balance"] = max(0, float(rules["min_outstanding_balance"] or 0))
    rules["stages"] = [str(item).strip() for item in (rules.get("stages") or []) if str(item).strip()]
    rules["priorities"] = [str(item).strip() for item in (rules.get("priorities") or []) if str(item).strip()]
    for key in ("exclude_active_promises", "exclude_legal_handover", "share_national_id", "share_employment"):
        rules[key] = bool(rules[key])
    return rules


def eligible_case(case: Any, rules: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if int(case.days_past_due or 0) < int(rules["min_days_past_due"]):
        reasons.append("days_past_due")
    if float(case.overdue_amount or 0) < float(rules["min_overdue_amount"]):
        reasons.append("overdue_amount")
    if float(case.outstanding_balance or 0) < float(rules["min_outstanding_balance"]):
        reasons.append("outstanding_balance")
    if rules["stages"] and str(case.stage or "") not in set(rules["stages"]):
        reasons.append("stage")
    if rules["priorities"] and str(case.priority or "") not in set(rules["priorities"]):
        reasons.append("priority")
    if rules["exclude_active_promises"] and str(case.promise_status or "").lower() in {
        "active", "open", "pending", "promised", "kept_pending"
    }:
        reasons.append("active_promise")
    if rules["exclude_legal_handover"] and case.legal_handover_at is not None:
        reasons.append("legal_handover")
    if str(case.status or "").lower() in {"closed", "resolved", "written_off"}:
        reasons.append("closed_case")
    return not reasons, reasons


def canonical_body(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str).encode("utf-8")


def bridge_headers(*, bridge_token: str, idempotency_key: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        BRIDGE_TOKEN_HEADER: bridge_token,
        IDEMPOTENCY_HEADER: idempotency_key,
    }


async def post_to_lelefa(
    path: str,
    payload: dict[str, Any],
    *,
    bridge_token: str,
    idempotency_key: str,
) -> dict[str, Any]:
    body = canonical_body(payload)
    async with httpx.AsyncClient(timeout=integration_timeout_seconds()) as client:
        response = await client.post(
            f"{LELEFA_API_BASE_URL}{path}",
            content=body,
            headers=bridge_headers(bridge_token=bridge_token, idempotency_key=idempotency_key),
        )
        response.raise_for_status()
        if not response.content:
            return {}
        value = response.json()
        return value if isinstance(value, dict) else {"data": value}


def delivery_state(status: str, *, message: str | None = None, remote: dict | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "message": message,
        "remote": remote or {},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
