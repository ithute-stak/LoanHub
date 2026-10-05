from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.access_control import (
    LENDING_ROLES,
    TenantContext,
    assert_branch_scope,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.credit_bureau import CreditBureauProviderPayload
from database.models.enums import UserRole
from database.models.lending_operations import CreditBureauEnquiry
from database.models.origination import BorrowerDebtObligation, OriginationIntegrationConfiguration
from database.models.platform_credit_bureau import PlatformCreditBureauConfiguration
from database.models.professional_lending import DirectLoanApplication
from database.schemas.credit_bureau import ExperianEnquiryRequest
from database.session import get_db
from routers.credit_bureau_configuration import company_experian_preview
from services.credential_service import encrypt_credential
from services.credit_bureau_policy_service import company_experian_policy, latest_fresh_experian_enquiry
from services.credit_bureau_payg_service import (
    accrue_successful_enquiry,
    company_transactions,
    require_approved_subscription,
)
from services.experian_service import (
    ExperianConfigurationError,
    ExperianRequestError,
    environment_test_status,
    has_credentials_for_environment,
    run_bureau_enquiry,
)
from services.origination_service import borrower_identity


router = APIRouter(prefix="/credit-bureau", tags=["Credit Bureau"])

BUREAU_VIEW_ROLES = LENDING_ROLES | {
    UserRole.RISK_MANAGER,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.AUDITOR,
    UserRole.DATA_PROTECTION_OFFICER,
}
BUREAU_RUN_ROLES = LENDING_ROLES | {
    UserRole.RISK_MANAGER,
    UserRole.COMPLIANCE_OFFICER,
}


def _application(db: Session, *, application_id: UUID, context: TenantContext) -> DirectLoanApplication:
    application = (
        db.query(DirectLoanApplication)
        .filter(
            DirectLoanApplication.id == application_id,
            DirectLoanApplication.company_id == context.company_id,
        )
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Origination application not found")
    assert_branch_scope(context, application.branch_id)
    return application


def _company_integration(db: Session, *, context: TenantContext) -> OriginationIntegrationConfiguration:
    row = (
        db.query(OriginationIntegrationConfiguration)
        .filter(
            OriginationIntegrationConfiguration.company_id == context.company_id,
            OriginationIntegrationConfiguration.provider == "experian",
        )
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=409,
            detail="This lending company does not yet have an approved Credit Bureau subscription",
        )
    return row


def _platform_integration(db: Session, *, environment: str) -> PlatformCreditBureauConfiguration:
    row = (
        db.query(PlatformCreditBureauConfiguration)
        .filter(PlatformCreditBureauConfiguration.provider == "experian")
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=409,
            detail="The Platform Owner has not configured Experian yet",
        )
    if not row.is_enabled:
        raise HTTPException(
            status_code=409,
            detail="Experian is disabled at platform level. Contact the LoanHub Platform Owner.",
        )
    if not has_credentials_for_environment(row, environment):
        raise HTTPException(
            status_code=409,
            detail=f"The Platform Owner has not configured Experian {environment.title()} credentials",
        )
    if environment_test_status(row, environment) != "connected":
        raise HTTPException(
            status_code=409,
            detail=f"The Experian {environment.title()} connection has not passed its latest connectivity test",
        )
    return row


def _experian_enquiry_metadata(row: CreditBureauEnquiry) -> dict:
    data = dict(row.enquiry_data or {})
    value = data.get("experian")
    return dict(value) if isinstance(value, dict) else {}


def _normalized_response(row: CreditBureauEnquiry) -> dict:
    data = dict(row.response_data or {})
    value = data.get("normalized")
    return dict(value) if isinstance(value, dict) else {}


def _failure_parts(row: CreditBureauEnquiry) -> tuple[str | None, str | None]:
    text = str(row.failure_reason or "").strip()
    if not text:
        return None, None
    code, separator, message = text.partition(":")
    return (code.strip() or None, message.strip() if separator else text)


def _enquiry_payload(row: CreditBureauEnquiry) -> dict:
    """Return the company-safe Experian summary without provider secrets."""
    metadata = _experian_enquiry_metadata(row)
    normalized = _normalized_response(row)
    error_code, error_message = _failure_parts(row)
    status_value = {
        "requested": "pending",
        "processing": "pending",
        "completed": "succeeded",
    }.get(str(row.status or ""), str(row.status or "pending"))
    defaults_count = int(normalized.get("defaults_count") or 0)
    judgments_count = int(normalized.get("judgments_count") or 0)
    collections_count = int(normalized.get("collections_count") or 0)
    return {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "branch_id": str(row.branch_id) if row.branch_id else None,
        "borrower_id": str(row.borrower_id),
        "application_id": str(row.application_id) if row.application_id else None,
        "provider": row.provider,
        "enquiry_type": "credit_application",
        "permissible_purpose": str(metadata.get("permissible_purpose") or row.purpose or "credit_application"),
        "consent_confirmed": bool(row.consent_confirmed),
        "consent_method": metadata.get("consent_method"),
        "consent_reference": metadata.get("consent_reference"),
        "consent_captured_at": metadata.get("consent_captured_at"),
        "status": status_value,
        "provider_reference": normalized.get("provider_reference"),
        "requested_at": row.requested_at,
        "completed_at": row.completed_at,
        "score": row.score,
        "risk_band": row.risk_grade,
        "identity_match": normalized.get("identity_match"),
        "open_accounts_count": int(row.existing_accounts or 0),
        "defaults_count": defaults_count,
        "judgments_count": judgments_count,
        "collections_count": collections_count,
        "recent_enquiries_count": int(normalized.get("recent_enquiries_count") or 0),
        "monthly_commitments": float(row.monthly_obligations or 0),
        "total_balance": float(row.current_exposure or 0),
        "normalized_result": normalized,
        "error_code": error_code,
        "error_message": error_message,
        "requested_by_user_id": str(row.requested_by_user_id) if row.requested_by_user_id else None,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _fail_enquiry(db: Session, row: CreditBureauEnquiry, *, code: str, message: str) -> None:
    row.status = "failed"
    row.failure_reason = f"{code}: {message}"[:1000]
    row.completed_at = datetime.now(timezone.utc)
    db.commit()


@router.get("/experian/configuration")
def get_experian_configuration(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, BUREAU_VIEW_ROLES)
    return company_experian_preview(db, company_id=context.company_id)


@router.post("/experian/test-connection")
def test_experian_connection_from_company(
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, BUREAU_VIEW_ROLES)
    raise HTTPException(
        status_code=403,
        detail="Experian connectivity testing is controlled by the LoanHub Platform Owner under API & integrations",
    )


@router.get("/applications/{application_id}/enquiries")
def list_application_enquiries(
    application_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, BUREAU_VIEW_ROLES)
    application = _application(db, application_id=application_id, context=context)
    rows = (
        db.query(CreditBureauEnquiry)
        .filter(
            CreditBureauEnquiry.company_id == context.company_id,
            CreditBureauEnquiry.application_id == application.id,
            CreditBureauEnquiry.provider == "experian",
        )
        .order_by(CreditBureauEnquiry.requested_at.desc())
        .limit(50)
        .all()
    )
    return [_enquiry_payload(row) for row in rows]


@router.get("/applications/{application_id}/decision-context")
def application_decision_context(
    application_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, BUREAU_VIEW_ROLES)
    application = _application(db, application_id=application_id, context=context)
    declared = (
        db.query(func.coalesce(func.sum(BorrowerDebtObligation.monthly_installment), 0))
        .filter(
            BorrowerDebtObligation.borrower_id == application.borrower_id,
            BorrowerDebtObligation.status.in_(("active", "defaulted", "restructured", "unknown")),
            BorrowerDebtObligation.current_balance > 0,
        )
        .scalar()
        or Decimal("0")
    )
    latest = (
        db.query(CreditBureauEnquiry)
        .filter(
            CreditBureauEnquiry.company_id == context.company_id,
            CreditBureauEnquiry.application_id == application.id,
            CreditBureauEnquiry.borrower_id == application.borrower_id,
            CreditBureauEnquiry.provider == "experian",
            CreditBureauEnquiry.status == "completed",
        )
        .order_by(CreditBureauEnquiry.completed_at.desc(), CreditBureauEnquiry.requested_at.desc())
        .first()
    )
    bureau_monthly = Decimal(latest.monthly_obligations or 0) if latest else None
    normalized = _normalized_response(latest) if latest else {}
    return {
        "application_id": str(application.id),
        "declared_monthly_debt": float(declared),
        "bureau_monthly_commitments": float(bureau_monthly) if bureau_monthly is not None else None,
        "bureau_total_balance": float(latest.current_exposure or 0) if latest else None,
        "variance": float(bureau_monthly - Decimal(declared)) if bureau_monthly is not None else None,
        "score": latest.score if latest else None,
        "risk_band": latest.risk_grade if latest else None,
        "defaults_count": int(normalized.get("defaults_count") or 0) if latest else None,
        "latest_enquiry_id": str(latest.id) if latest else None,
        "latest_enquiry_status": "succeeded" if latest else None,
    }


@router.get("/enquiries/{enquiry_id}")
def get_enquiry(
    enquiry_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, BUREAU_VIEW_ROLES)
    row = (
        db.query(CreditBureauEnquiry)
        .filter(
            CreditBureauEnquiry.id == enquiry_id,
            CreditBureauEnquiry.company_id == context.company_id,
            CreditBureauEnquiry.provider == "experian",
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Experian credit-bureau enquiry not found")
    assert_branch_scope(context, row.branch_id)
    return _enquiry_payload(row)


@router.post("/applications/{application_id}/experian", status_code=status.HTTP_201_CREATED)
def run_experian_credit_check(
    application_id: UUID,
    payload: ExperianEnquiryRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, BUREAU_RUN_ROLES)
    application = _application(db, application_id=application_id, context=context)
    subscription = require_approved_subscription(db, company_id=context.company_id)
    company_integration = _company_integration(db, context=context)
    if not company_integration.is_enabled:
        raise HTTPException(status_code=409, detail="Credit Bureau access is not active for this lending company")
    company_policy = dict(company_integration.configuration or {})
    selected_environment = str(company_policy.get("environment") or company_integration.environment or "sandbox")
    selected_environment = "live" if selected_environment.lower() in {"live", "production"} else "sandbox"
    platform_integration = _platform_integration(db, environment=selected_environment)

    identity = borrower_identity(db, application.borrower_id)
    if not identity.get("national_id") and not identity.get("passport_number"):
        raise HTTPException(status_code=409, detail="Record the borrower's National ID or passport before running Experian")

    now = datetime.now(timezone.utc)
    _, company_policy = company_experian_policy(db, context.company_id)
    if not payload.force_refresh:
        reusable = latest_fresh_experian_enquiry(
            db,
            company_id=context.company_id,
            application_id=application.id,
            borrower_id=application.borrower_id,
            max_report_age_hours=int(company_policy["max_report_age_hours"]),
            environment=selected_environment,
        )
        if reusable:
            return _enquiry_payload(reusable)
    consent_reference = (payload.consent_reference or "").strip() or None
    enquiry = CreditBureauEnquiry(
        company_id=context.company_id,
        branch_id=application.branch_id,
        borrower_id=application.borrower_id,
        application_id=application.id,
        provider="experian",
        enquiry_reference=f"EXP-{uuid4().hex[:24].upper()}",
        purpose=payload.permissible_purpose,
        consent_confirmed=True,
        status="requested",
        enquiry_data={
            "experian": {
                "permissible_purpose": payload.permissible_purpose,
                "consent_method": payload.consent_method,
                "consent_reference": consent_reference,
                "consent_captured_at": now.isoformat(),
                "connection_scope": "platform",
                "environment": selected_environment,
                "enquiry_purpose": payload.enquiry_purpose,
                "result_type": payload.result_type,
                "requested_blocks": {
                    "cs_data": payload.cs_data,
                    "cpa_plus_nlr_data": payload.cpa_plus_nlr_data,
                    "deeds": payload.deeds,
                    "directors": payload.directors,
                    "run_compuscore": payload.run_compuscore,
                    "run_codix": payload.run_codix,
                },
            }
        },
        response_data={},
        requested_at=now,
        requested_by_user_id=context.user.id,
    )
    db.add(enquiry)
    db.commit()
    db.refresh(enquiry)

    gender_value = str(identity.get("gender") or "").strip().lower()
    gender = "M" if gender_value in {"m", "male", "gender.male"} else "F" if gender_value in {"f", "female", "gender.female"} else None
    provider_context = {
        "borrower_id": str(application.borrower_id),
        "application_id": str(application.id),
        "application_reference": application.application_reference,
        "requested_amount": float(application.requested_amount or 0),
        "term_count": int(application.term_count or 0),
        "purpose": application.purpose,
        "full_name": identity.get("full_name"),
        "forename": identity.get("first_name"),
        "forename2": identity.get("middle_name"),
        "forename3": "",
        "surname": identity.get("last_name"),
        "gender": gender,
        "national_id": identity.get("national_id"),
        "passport_number": identity.get("passport_number"),
        "date_of_birth": identity.get("date_of_birth").isoformat() if identity.get("date_of_birth") else None,
        "address1": payload.address1 or identity.get("physical_address"),
        "address2": payload.address2 or identity.get("town_or_village") or identity.get("district"),
        "address3": payload.address3 or "",
        "address4": payload.address4 or "",
        "postal_code": payload.postal_code,
        "cell_tel_no": identity.get("phone"),
        "permissible_purpose": payload.permissible_purpose,
        "consent_reference": consent_reference,
        "enquiry_purpose": payload.enquiry_purpose,
        "result_type": payload.result_type,
        "cs_data": payload.cs_data,
        "cpa_plus_nlr_data": payload.cpa_plus_nlr_data,
        "deeds": payload.deeds,
        "directors": payload.directors,
        "run_compuscore": payload.run_compuscore,
        "run_codix": payload.run_codix,
        "address_mandatory": True,
        "environment": selected_environment,
    }

    try:
        normalized, raw = run_bureau_enquiry(platform_integration, context=provider_context)
    except ExperianConfigurationError as error:
        _fail_enquiry(db, enquiry, code="experian_configuration_error", message=str(error))
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ExperianRequestError as error:
        _fail_enquiry(db, enquiry, code=error.code, message=str(error))
        raise HTTPException(status_code=502, detail=str(error)) from error

    defaults_count = int(normalized.get("defaults_count") or 0)
    judgments_count = int(normalized.get("judgments_count") or 0)
    collections_count = int(normalized.get("collections_count") or 0)
    enquiry.status = "completed"
    enquiry.score = normalized.get("score")
    enquiry.risk_grade = str(normalized.get("risk_band") or "")[:40] or None
    enquiry.existing_accounts = int(normalized.get("open_accounts_count") or 0)
    enquiry.current_exposure = Decimal(str(normalized.get("total_balance") or 0))
    enquiry.monthly_obligations = Decimal(str(normalized.get("monthly_commitments") or 0))
    enquiry.adverse_records = defaults_count + judgments_count + collections_count
    enquiry.response_data = {"normalized": normalized}
    enquiry.completed_at = datetime.now(timezone.utc)
    provider_payload = CreditBureauProviderPayload(
        enquiry_id=enquiry.id,
        company_id=context.company_id,
        provider="experian",
        raw_response_encrypted=encrypt_credential(json.dumps(raw, separators=(",", ":"), default=str)),
    )
    db.add(enquiry)
    db.add(provider_payload)
    accrue_successful_enquiry(
        db,
        subscription=subscription,
        enquiry_id=enquiry.id,
        environment=selected_environment,
    )
    db.commit()
    db.refresh(enquiry)
    return _enquiry_payload(enquiry)


@router.get("/experian/transactions")
def list_company_experian_transactions(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
    limit: int = 100,
):
    require_tenant_roles(context, BUREAU_VIEW_ROLES)
    return company_transactions(db, company_id=context.company_id, limit=limit)
