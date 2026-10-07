from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from database.models.lending_operations import CDASPayrollProfile, CreditBureauEnquiry


MONEY = Decimal("0.01")


def money(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def normalized_bureau(enquiry: CreditBureauEnquiry | None) -> dict[str, Any]:
    if not enquiry:
        return {}
    response = dict(enquiry.response_data or {})
    value = response.get("normalized")
    return dict(value) if isinstance(value, dict) else {}


def bureau_evidence(
    enquiry: CreditBureauEnquiry | None,
    *,
    policy: dict[str, Any],
    application_id,
) -> dict[str, Any]:
    normalized = normalized_bureau(enquiry)
    score = enquiry.score if enquiry else None
    defaults_count = int(normalized.get("defaults_count") or 0)
    judgments_count = int(normalized.get("judgments_count") or 0)
    collections_count = int(normalized.get("collections_count") or 0)
    recent_enquiries_count = int(normalized.get("recent_enquiries_count") or 0)
    identity_match = normalized.get("identity_match") if enquiry else None

    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    action_path = f"/company/origination/experian?application={application_id}"

    if enquiry:
        decline_below = policy.get("decline_below_score")
        refer_below = policy.get("refer_below_score")
        if decline_below is not None and score is not None and score < int(decline_below):
            blockers.append({
                "source": "bureau",
                "code": "score_below_decline_threshold",
                "message": "The latest Experian score is below the company's configured decline threshold.",
                "action_path": action_path,
            })
        elif refer_below is not None and score is not None and score < int(refer_below):
            warnings.append({
                "source": "bureau",
                "code": "score_requires_referral",
                "message": "The latest Experian score is below the company's referral threshold and requires manager attention.",
                "action_path": action_path,
            })

        if policy.get("block_defaults") and defaults_count > 0:
            blockers.append({
                "source": "bureau",
                "code": "defaults_blocked",
                "message": "Experian reports defaults and company policy blocks approval.",
                "action_path": action_path,
            })
        if policy.get("block_judgments") and judgments_count > 0:
            blockers.append({
                "source": "bureau",
                "code": "judgments_blocked",
                "message": "Experian reports judgments and company policy blocks approval.",
                "action_path": action_path,
            })
        if policy.get("block_collections") and collections_count > 0:
            blockers.append({
                "source": "bureau",
                "code": "collections_blocked",
                "message": "Experian reports collection records and company policy blocks approval.",
                "action_path": action_path,
            })
        if policy.get("require_identity_match") and identity_match is not True:
            blockers.append({
                "source": "bureau",
                "code": "identity_match_required",
                "message": "Experian identity matching has not passed the company's approval policy.",
                "action_path": action_path,
            })

    return {
        "enquiry_id": str(enquiry.id) if enquiry else None,
        "reference": enquiry.enquiry_reference if enquiry else None,
        "completed_at": enquiry.completed_at.isoformat() if enquiry and enquiry.completed_at else None,
        "score": score,
        "risk_band": enquiry.risk_grade if enquiry else None,
        "monthly_commitments": str(money(enquiry.monthly_obligations)) if enquiry else "0.00",
        "total_balance": str(money(enquiry.current_exposure)) if enquiry else "0.00",
        "defaults_count": defaults_count,
        "judgments_count": judgments_count,
        "collections_count": collections_count,
        "recent_enquiries_count": recent_enquiries_count,
        "identity_match": identity_match,
        "policy": {
            "decline_below_score": policy.get("decline_below_score"),
            "refer_below_score": policy.get("refer_below_score"),
            "block_defaults": bool(policy.get("block_defaults")),
            "block_judgments": bool(policy.get("block_judgments")),
            "block_collections": bool(policy.get("block_collections")),
            "require_identity_match": bool(policy.get("require_identity_match")),
            "include_bureau_commitments_in_affordability": bool(
                policy.get("include_bureau_commitments_in_affordability")
            ),
            "bureau_debt_mode": str(policy.get("bureau_debt_mode") or "max"),
        },
        "blockers": blockers,
        "warnings": warnings,
    }


def cdas_deduction_capacity(
    profile: CDASPayrollProfile | None,
    *,
    selected_for_collection: bool,
    proposed_installment: Decimal | int | float | str | None,
    application_id,
    live_affordability: Decimal | int | float | str | None = None,
) -> dict[str, Any]:
    net_salary = money(profile.net_salary if profile else 0)
    existing_deductions = money(profile.existing_deductions if profile else 0)
    maximum_percent = Decimal(str(profile.maximum_deduction_percent or 0)) if profile else Decimal("0")
    maximum_deduction = money(net_salary * maximum_percent / Decimal("100"))
    calculated_capacity = money(max(maximum_deduction - existing_deductions, Decimal("0")))
    provider_capacity = money(live_affordability) if live_affordability is not None else None
    available_capacity = min(calculated_capacity, provider_capacity) if provider_capacity is not None else calculated_capacity
    proposed = money(proposed_installment)
    verified = bool(
        profile
        and profile.verified
        and str(profile.employee_number or "").strip()
    )
    capacity_sufficient = not selected_for_collection or (
        verified and proposed <= available_capacity
    )

    blockers: list[dict[str, str]] = []
    if selected_for_collection and verified and proposed > available_capacity:
        blockers.append({
            "source": "cdas",
            "code": "deduction_capacity_insufficient",
            "message": (
                "The proposed installment exceeds the borrower's verified CDAS payroll deduction capacity."
            ),
            "action_path": f"/company/cdas?application={application_id}",
        })

    return {
        "profile_id": str(profile.id) if profile else None,
        "verified": verified,
        "verified_at": profile.verified_at.isoformat() if profile and profile.verified_at else None,
        "verification_reference": profile.verification_reference if profile else None,
        "employee_number": profile.employee_number if profile else None,
        "net_salary": str(net_salary),
        "existing_deductions": str(existing_deductions),
        "maximum_deduction_percent": str(maximum_percent),
        "maximum_deduction": str(maximum_deduction),
        "calculated_deduction_capacity": str(calculated_capacity),
        "live_affordability": str(provider_capacity) if provider_capacity is not None else None,
        "available_deduction_capacity": str(available_capacity),
        "capacity_source": "minimum_of_profile_and_live_cdas" if provider_capacity is not None else "verified_profile",
        "proposed_installment": str(proposed),
        "capacity_sufficient": capacity_sufficient,
        "blockers": blockers,
    }


def external_evidence_snapshot(
    *,
    application_id,
    bureau: CreditBureauEnquiry | None,
    bureau_policy: dict[str, Any],
    cdas_profile: CDASPayrollProfile | None,
    cdas_selected: bool,
    proposed_installment: Decimal | int | float | str | None,
    live_cdas_affordability: Decimal | int | float | str | None = None,
) -> dict[str, Any]:
    bureau_value = bureau_evidence(
        bureau,
        policy=bureau_policy,
        application_id=application_id,
    )
    cdas_value = cdas_deduction_capacity(
        cdas_profile,
        selected_for_collection=cdas_selected,
        proposed_installment=proposed_installment,
        application_id=application_id,
        live_affordability=live_cdas_affordability,
    )
    return {
        "credit_bureau": bureau_value,
        "cdas": cdas_value,
        "debt_counting": {
            "bureau_commitments_mode": str(bureau_policy.get("bureau_debt_mode") or "max"),
            "bureau_commitments_in_affordability": bool(
                bureau_policy.get("include_bureau_commitments_in_affordability")
            ),
            "cdas_existing_deductions_are_capacity_only": True,
            "live_cdas_affordability_used": live_cdas_affordability is not None,
            "note": (
                "CDAS existing deductions constrain payroll collection capacity and are not "
                "subtracted again from affordability debt commitments."
            ),
        },
    }
