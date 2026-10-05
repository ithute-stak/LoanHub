from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from database.models.lending_operations import CDASPayrollProfile
from database.models.origination import AffordabilityAssessment, BorrowerEmploymentProfile, BorrowerKYCProfile
from database.models.platform_credit_bureau import PlatformCreditBureauConfiguration
from database.models.professional_lending import DirectLoanApplication
from services.cdas_config_service import configuration_summary as cdas_configuration_summary, get_configuration as get_cdas_configuration
from services.credit_bureau_policy_service import (
    company_experian_policy,
    experian_required_for_application,
    latest_fresh_experian_enquiry,
)
from services.experian_service import environment_test_status, has_credentials_for_environment
from services.external_underwriting_evidence_service import (
    bureau_evidence,
    cdas_deduction_capacity,
)


def _assessment_decision(assessment: AffordabilityAssessment | None) -> str | None:
    if not assessment:
        return None
    return assessment.override_decision if assessment.overridden else assessment.decision


def application_integration_readiness(
    db: Session,
    *,
    application: DirectLoanApplication,
    amount: Decimal | None = None,
    product_id=None,
) -> dict[str, Any]:
    """Build one cross-system view of Core LoanHub, Experian and CDAS.

    This function never contacts an external provider. It only reads durable
    LoanHub state that was produced by the normal Core, Experian and CDAS flows.
    """
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    kyc = (
        db.query(BorrowerKYCProfile)
        .filter(BorrowerKYCProfile.borrower_id == application.borrower_id)
        .first()
    )
    assessment = (
        db.get(AffordabilityAssessment, application.affordability_assessment_id)
        if application.affordability_assessment_id
        else None
    )
    affordability_decision = _assessment_decision(assessment)

    core_ready = True
    if application.channel == "credit_origination" and affordability_decision not in {
        "eligible",
        "conditionally_eligible",
    }:
        core_ready = False
        blockers.append(
            {
                "source": "core",
                "code": "affordability_not_positive",
                "message": "Core LoanHub requires a positive affordability decision before approval.",
                "action_path": f"/company/origination/new?application={application.id}",
            }
        )

    bureau_row, bureau_policy = company_experian_policy(db, application.company_id)
    bureau_enabled = bool(bureau_row and bureau_row.is_enabled)
    bureau_environment = str(bureau_policy.get("environment") or "sandbox")
    platform_bureau = (
        db.query(PlatformCreditBureauConfiguration)
        .filter(PlatformCreditBureauConfiguration.provider == "experian")
        .first()
    )
    bureau_platform_ready = bool(
        platform_bureau
        and platform_bureau.is_enabled
        and has_credentials_for_environment(platform_bureau, bureau_environment)
        and environment_test_status(platform_bureau, bureau_environment) == "connected"
    )
    bureau_required_affordability = bool(
        bureau_enabled
        and experian_required_for_application(
            bureau_policy,
            application,
            stage="affordability",
            amount=amount,
            product_id=product_id,
        )
    )
    bureau_required_approval = bool(
        bureau_enabled
        and experian_required_for_application(
            bureau_policy,
            application,
            stage="approval",
            amount=amount,
            product_id=product_id,
        )
    )
    latest_bureau = None
    if bureau_enabled:
        latest_bureau = latest_fresh_experian_enquiry(
            db,
            company_id=application.company_id,
            application_id=application.id,
            borrower_id=application.borrower_id,
            max_report_age_hours=int(bureau_policy["max_report_age_hours"]),
            environment=bureau_environment,
        )
    bureau_fresh = latest_bureau is not None
    bureau_ready = not bureau_required_approval or bureau_fresh
    bureau_snapshot = bureau_evidence(
        latest_bureau,
        policy=bureau_policy,
        application_id=application.id,
    )

    if bureau_fresh and latest_bureau:
        if bureau_snapshot["blockers"]:
            bureau_ready = False
            blockers.extend(bureau_snapshot["blockers"])
        warnings.extend(bureau_snapshot["warnings"])

        if bureau_policy.get("include_bureau_commitments_in_affordability") and assessment:
            input_snapshot = dict(assessment.input_snapshot or {})
            bureau_snapshot = input_snapshot.get("credit_bureau")
            bureau_snapshot = dict(bureau_snapshot) if isinstance(bureau_snapshot, dict) else {}
            assessment_enquiry_id = str(bureau_snapshot.get("enquiry_id") or "")
            if assessment_enquiry_id != str(latest_bureau.id):
                core_ready = False
                blockers.append(
                    {
                        "source": "core",
                        "code": "affordability_stale_after_bureau",
                        "message": "A newer Experian report is available than the one used for affordability. Recalculate affordability before approval.",
                        "action_path": f"/company/origination/new?application={application.id}",
                    }
                )

    if bureau_required_approval and not bureau_fresh:
        blockers.append(
            {
                "source": "bureau",
                "code": "fresh_report_required",
                "message": "A fresh Experian report is required by company policy before approval.",
                "action_path": f"/company/origination/experian?application={application.id}",
            }
        )
    elif bureau_enabled and not bureau_fresh:
        warnings.append(
            {
                "source": "bureau",
                "code": "no_fresh_report",
                "message": "Experian is enabled, but this application has no fresh report in the selected environment.",
                "action_path": f"/company/origination/experian?application={application.id}",
            }
        )

    if bureau_enabled and not bureau_platform_ready:
        warnings.append(
            {
                "source": "bureau",
                "code": "platform_connection_not_ready",
                "message": "The selected Experian environment is not currently ready at platform level. Existing fresh evidence remains visible, but a new bureau check cannot run until the platform connection is restored.",
                "action_path": f"/company/origination/experian?application={application.id}",
            }
        )

    cdas_config = cdas_configuration_summary(
        get_cdas_configuration(db, application.company_id)
    )
    cdas_provider_configured = bool(cdas_config.get("configured"))
    cdas_provider_enabled = bool(cdas_config.get("enabled"))
    cdas_provider_tested = str(cdas_config.get("last_test_status") or "") == "connected"

    cdas_profile = (
        db.query(CDASPayrollProfile)
        .filter(
            CDASPayrollProfile.company_id == application.company_id,
            CDASPayrollProfile.borrower_id == application.borrower_id,
        )
        .first()
    )
    employment = (
        db.query(BorrowerEmploymentProfile)
        .filter(BorrowerEmploymentProfile.borrower_id == application.borrower_id)
        .first()
    )
    cdas_selected = bool(application.cdas_collection_enabled)
    cdas_verified = bool(
        cdas_profile
        and cdas_profile.verified
        and str(cdas_profile.employee_number or "").strip()
    )
    cdas_capacity = cdas_deduction_capacity(
        cdas_profile,
        selected_for_collection=cdas_selected,
        proposed_installment=(assessment.proposed_installment if assessment else 0),
        application_id=application.id,
    )
    cdas_ready = not cdas_selected or (
        cdas_verified
        and cdas_provider_configured
        and cdas_provider_enabled
        and bool(cdas_capacity["capacity_sufficient"])
    )
    if cdas_selected and not cdas_verified:
        blockers.append(
            {
                "source": "cdas",
                "code": "payroll_profile_not_verified",
                "message": "CDAS collection is selected, but the borrower does not yet have a verified CDAS payroll profile.",
                "action_path": f"/company/cdas?application={application.id}",
            }
        )

    if cdas_selected and cdas_verified and not cdas_capacity["capacity_sufficient"]:
        blockers.extend(cdas_capacity["blockers"])

    if cdas_selected and not cdas_provider_configured:
        blockers.append(
            {
                "source": "cdas",
                "code": "company_connection_not_configured",
                "message": "CDAS collection is selected, but this company has not completed its CDAS connection configuration.",
                "action_path": "/company/settings?tab=cdas",
            }
        )
    elif cdas_selected and not cdas_provider_enabled:
        blockers.append(
            {
                "source": "cdas",
                "code": "company_connection_disabled",
                "message": "CDAS collection is selected, but CDAS is disabled for this company.",
                "action_path": "/company/settings",
            }
        )
    elif cdas_selected and not cdas_provider_tested:
        warnings.append(
            {
                "source": "cdas",
                "code": "company_connection_not_tested",
                "message": "The CDAS connection has not passed its latest login test. Verify it before registering the approved loan.",
                "action_path": "/company/settings",
            }
        )

    employment_employee_number = str(employment.employee_number or "").strip() if employment else ""
    cdas_employee_number = str(cdas_profile.employee_number or "").strip() if cdas_profile else ""
    if (
        cdas_selected
        and cdas_verified
        and employment_employee_number
        and cdas_employee_number
        and employment_employee_number.casefold() != cdas_employee_number.casefold()
    ):
        warnings.append(
            {
                "source": "cdas",
                "code": "employee_number_mismatch",
                "message": "The employee number in Core LoanHub employment data differs from the verified CDAS employee number.",
                "action_path": f"/company/origination/new?application={application.id}",
            }
        )

    ready_for_affordability = not (
        bureau_required_affordability and not bureau_fresh
    )
    ready_for_approval = bool(core_ready and bureau_ready and cdas_ready)

    hard_decline_codes = {
        "affordability_not_positive",
        "score_below_decline_threshold",
        "defaults_blocked",
        "identity_match_required",
        "judgments_blocked",
        "collections_blocked",
        "deduction_capacity_insufficient",
    }
    blocker_codes = {item["code"] for item in blockers}
    if ready_for_approval:
        final_decision = "loanable"
    elif blocker_codes & hard_decline_codes:
        final_decision = "not_loanable"
    else:
        final_decision = "action_required"

    return {
        "application_id": str(application.id),
        "application_reference": application.application_reference,
        "borrower_id": str(application.borrower_id),
        "ready_for_affordability": ready_for_affordability,
        "ready_for_approval": ready_for_approval,
        "final_decision": final_decision,
        "blockers": blockers,
        "warnings": warnings,
        "core": {
            "status": application.status,
            "kyc_status": kyc.status if kyc else None,
            "affordability_decision": affordability_decision,
            "affordability_assessment_id": str(assessment.id) if assessment else None,
            "ready_for_approval": core_ready,
        },
        "bureau": {
            "enabled": bureau_enabled,
            "environment": bureau_environment,
            "platform_ready": bureau_platform_ready,
            "requirement_mode": str(bureau_policy.get("requirement_mode") or "optional"),
            "required_before_affordability": bureau_required_affordability,
            "required_before_approval": bureau_required_approval,
            "fresh": bureau_fresh,
            "max_report_age_hours": int(bureau_policy["max_report_age_hours"]),
            "enquiry_id": str(latest_bureau.id) if latest_bureau else None,
            "completed_at": latest_bureau.completed_at.isoformat() if latest_bureau and latest_bureau.completed_at else None,
            "score": latest_bureau.score if latest_bureau else None,
            "risk_band": latest_bureau.risk_grade if latest_bureau else None,
            "monthly_commitments": float(latest_bureau.monthly_obligations or 0) if latest_bureau else None,
            "total_balance": float(latest_bureau.current_exposure or 0) if latest_bureau else None,
            "defaults_count": bureau_snapshot["defaults_count"] if latest_bureau else None,
            "judgments_count": bureau_snapshot["judgments_count"] if latest_bureau else None,
            "collections_count": bureau_snapshot["collections_count"] if latest_bureau else None,
            "recent_enquiries_count": bureau_snapshot["recent_enquiries_count"] if latest_bureau else None,
            "identity_match": bureau_snapshot["identity_match"] if latest_bureau else None,
            "used_in_affordability": bool(
                bureau_enabled
                and bureau_fresh
                and bureau_policy.get("include_bureau_commitments_in_affordability")
            ),
            "debt_mode": str(bureau_policy.get("bureau_debt_mode") or "max"),
        },
        "cdas": {
            "selected_for_collection": cdas_selected,
            "provider_environment": cdas_config.get("environment"),
            "provider_configured": cdas_provider_configured,
            "provider_enabled": cdas_provider_enabled,
            "provider_tested": cdas_provider_tested,
            "payroll_profile_found": cdas_profile is not None,
            "verified": cdas_verified,
            "employee_number": cdas_profile.employee_number if cdas_profile else None,
            "department": cdas_profile.ministry_department if cdas_profile else None,
            "verified_at": cdas_profile.verified_at.isoformat() if cdas_profile and cdas_profile.verified_at else None,
            "net_salary": float(cdas_capacity["net_salary"]),
            "existing_deductions": float(cdas_capacity["existing_deductions"]),
            "maximum_deduction_percent": float(cdas_capacity["maximum_deduction_percent"]),
            "maximum_deduction": float(cdas_capacity["maximum_deduction"]),
            "available_deduction_capacity": float(cdas_capacity["available_deduction_capacity"]),
            "proposed_installment": float(cdas_capacity["proposed_installment"]),
            "capacity_sufficient": bool(cdas_capacity["capacity_sufficient"]),
            "collection_plan": dict(application.cdas_collection_plan or {}),
            "ready_for_approval": cdas_ready,
        },
    }


def assert_application_integration_readiness_for_approval(
    db: Session,
    *,
    application: DirectLoanApplication,
    amount: Decimal,
    product_id,
) -> dict[str, Any]:
    readiness = application_integration_readiness(
        db,
        application=application,
        amount=amount,
        product_id=product_id,
    )
    if not readiness["ready_for_approval"]:
        messages = [item["message"] for item in readiness["blockers"]]
        from fastapi import HTTPException

        raise HTTPException(
            status_code=409,
            detail={
                "message": "The application is not ready for approval.",
                "blockers": readiness["blockers"],
                "summary": " ".join(messages),
            },
        )
    return readiness
