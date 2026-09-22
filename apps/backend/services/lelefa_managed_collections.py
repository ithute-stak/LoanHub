from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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

DEFAULT_COLLECTION_CHARGE_POLICY: dict[str, Any] = {
    "enabled": False,
    "charge_type": "percentage",
    "rate_percent": 10.0,
    "fixed_amount": 0.0,
    "basis": "amount_referred",
    "minimum_days_past_due": 120,
    "cap_amount": None,
    "trigger": "external_collection_referral",
    "clause_version": "COLLECT-001",
    "requires_signed_contract": True,
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


def _decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value if value is not None else default))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


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


def normalize_collection_charge_policy(configuration: dict | None) -> dict[str, Any]:
    raw = dict(configuration or {})
    stored = raw.get("collection_charge") if isinstance(raw.get("collection_charge"), dict) else raw
    policy = dict(DEFAULT_COLLECTION_CHARGE_POLICY)
    for key in policy:
        if key in stored:
            policy[key] = stored[key]

    policy["enabled"] = bool(policy.get("enabled"))
    policy["charge_type"] = str(policy.get("charge_type") or "percentage").strip().lower()
    if policy["charge_type"] not in {"percentage", "fixed"}:
        policy["charge_type"] = "percentage"

    policy["rate_percent"] = float(min(Decimal("100"), max(Decimal("0"), _decimal(policy.get("rate_percent"), "10"))))
    policy["fixed_amount"] = float(max(Decimal("0"), _decimal(policy.get("fixed_amount"))))
    policy["basis"] = str(policy.get("basis") or "amount_referred").strip().lower()
    if policy["basis"] not in {"amount_referred", "overdue_amount"}:
        policy["basis"] = "amount_referred"

    policy["minimum_days_past_due"] = max(1, int(policy.get("minimum_days_past_due") or 120))
    cap = policy.get("cap_amount")
    policy["cap_amount"] = float(max(Decimal("0"), _decimal(cap))) if cap not in (None, "") else None
    policy["trigger"] = "external_collection_referral"
    policy["clause_version"] = str(policy.get("clause_version") or "COLLECT-001").strip()[:80] or "COLLECT-001"
    policy["requires_signed_contract"] = True
    return policy


def calculate_collection_charge(
    policy: dict[str, Any] | None,
    *,
    amount_referred: Any,
    overdue_amount: Any,
    days_past_due: int,
    contract_signed: bool,
) -> dict[str, Any]:
    """Calculate a contract-authorised charge without mutating the loan balance."""
    normalized = normalize_collection_charge_policy({"collection_charge": policy or {}})
    result: dict[str, Any] = {
        "authorized": bool(normalized["enabled"]),
        "status": "not_authorized",
        "charge_amount": "0.00",
        "basis_amount": "0.00",
        "charge_type": normalized["charge_type"],
        "rate_percent": str(normalized["rate_percent"]),
        "fixed_amount": f'{_decimal(normalized["fixed_amount"]):.2f}',
        "basis": normalized["basis"],
        "minimum_days_past_due": normalized["minimum_days_past_due"],
        "cap_amount": (
            f'{_decimal(normalized["cap_amount"]):.2f}'
            if normalized["cap_amount"] is not None
            else None
        ),
        "trigger": normalized["trigger"],
        "clause_version": normalized["clause_version"],
        "requires_signed_contract": True,
    }
    if not normalized["enabled"]:
        return result
    if not contract_signed:
        result["status"] = "contract_not_signed"
        return result
    if int(days_past_due or 0) < int(normalized["minimum_days_past_due"]):
        result["status"] = "minimum_arrears_not_met"
        return result

    referred = max(Decimal("0"), _decimal(amount_referred))
    overdue = max(Decimal("0"), _decimal(overdue_amount))
    basis_amount = referred if normalized["basis"] == "amount_referred" else overdue

    if normalized["charge_type"] == "fixed":
        charge = max(Decimal("0"), _decimal(normalized["fixed_amount"]))
    else:
        rate = max(Decimal("0"), _decimal(normalized["rate_percent"]))
        charge = basis_amount * rate / Decimal("100")

    cap_amount = normalized["cap_amount"]
    if cap_amount is not None:
        charge = min(charge, max(Decimal("0"), _decimal(cap_amount)))

    charge = charge.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    basis_amount = basis_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    result["basis_amount"] = f"{basis_amount:.2f}"
    result["charge_amount"] = f"{charge:.2f}"
    result["status"] = "assessable_on_external_referral" if charge > 0 else "zero_charge"
    return result


def collection_charge_disclosure(policy: dict[str, Any] | None) -> str:
    normalized = normalize_collection_charge_policy({"collection_charge": policy or {}})
    if not normalized["enabled"]:
        return "No borrower collection/recovery charge is authorised under this agreement."
    if normalized["charge_type"] == "fixed":
        pricing = f'LSL {_decimal(normalized["fixed_amount"]):,.2f}'
    else:
        basis = "the amount referred for external collection" if normalized["basis"] == "amount_referred" else "the overdue amount"
        pricing = f'{_decimal(normalized["rate_percent"]):g}% of {basis}'
    cap = ""
    if normalized["cap_amount"] is not None:
        cap = f', capped at LSL {_decimal(normalized["cap_amount"]):,.2f}'
    return (
        f"{pricing}{cap}; applicable only after at least "
        f'{normalized["minimum_days_past_due"]} days past due and external collection referral.'
    )


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
