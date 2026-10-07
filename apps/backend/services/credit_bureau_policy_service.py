from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models.lending_operations import CreditBureauEnquiry
from database.models.origination import OriginationIntegrationConfiguration
from database.models.professional_lending import DirectLoanApplication


DEFAULT_EXPERIAN_POLICY: dict[str, Any] = {
    "environment": "sandbox",
    "requirement_mode": "optional",
    "max_report_age_hours": 24,
    "required_above_amount": None,
    "required_product_ids": [],
    "block_defaults": False,
    "block_judgments": False,
    "block_collections": False,
    "require_identity_match": False,
}


def company_experian_policy(db: Session, company_id: UUID) -> tuple[OriginationIntegrationConfiguration | None, dict[str, Any]]:
    row = (
        db.query(OriginationIntegrationConfiguration)
        .filter(
            OriginationIntegrationConfiguration.company_id == company_id,
            OriginationIntegrationConfiguration.provider == "experian",
        )
        .first()
    )
    policy = dict(DEFAULT_EXPERIAN_POLICY)
    if row and isinstance(row.configuration, dict):
        policy.update(row.configuration)

    # Backward compatibility for companies configured before requirement_mode
    # was introduced.
    if policy.get("require_before_affordability") and policy.get("requirement_mode") == "optional":
        policy["requirement_mode"] = "before_affordability"

    policy["max_report_age_hours"] = max(
        1,
        min(int(policy.get("max_report_age_hours") or 24), 720),
    )
    product_ids = policy.get("required_product_ids")
    policy["required_product_ids"] = [str(value) for value in product_ids] if isinstance(product_ids, list) else []
    return row, policy


def latest_fresh_experian_enquiry(
    db: Session,
    *,
    company_id: UUID,
    application_id: UUID,
    borrower_id: UUID,
    max_report_age_hours: int,
    environment: str = "sandbox",
) -> CreditBureauEnquiry | None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_report_age_hours)
    rows = (
        db.query(CreditBureauEnquiry)
        .filter(
            CreditBureauEnquiry.company_id == company_id,
            CreditBureauEnquiry.application_id == application_id,
            CreditBureauEnquiry.borrower_id == borrower_id,
            CreditBureauEnquiry.provider == "experian",
            CreditBureauEnquiry.status == "completed",
            CreditBureauEnquiry.completed_at.isnot(None),
            CreditBureauEnquiry.completed_at >= cutoff,
        )
        .order_by(CreditBureauEnquiry.completed_at.desc(), CreditBureauEnquiry.requested_at.desc())
        .limit(50)
        .all()
    )
    selected_environment = "live" if str(environment).lower() in {"live", "production"} else "sandbox"
    for row in rows:
        metadata = dict(row.enquiry_data or {}).get("experian")
        metadata = dict(metadata) if isinstance(metadata, dict) else {}
        row_environment = "live" if str(metadata.get("environment") or "sandbox").lower() in {"live", "production"} else "sandbox"
        if row_environment == selected_environment:
            return row
    return None



def latest_fresh_borrower_experian_enquiry(
    db: Session,
    *,
    company_id: UUID,
    borrower_id: UUID,
    max_report_age_hours: int,
    environment: str = "sandbox",
) -> CreditBureauEnquiry | None:
    """Return the latest fresh borrower-level Experian evidence for quick underwriting.

    Marketplace/quick-loan offers do not always have a DirectLoanApplication,
    so they reuse the latest fresh enquiry for the same lender company and
    borrower. Environment still has to match the company's selected bureau mode.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_report_age_hours)
    rows = (
        db.query(CreditBureauEnquiry)
        .filter(
            CreditBureauEnquiry.company_id == company_id,
            CreditBureauEnquiry.borrower_id == borrower_id,
            CreditBureauEnquiry.provider == "experian",
            CreditBureauEnquiry.status == "completed",
            CreditBureauEnquiry.completed_at.isnot(None),
            CreditBureauEnquiry.completed_at >= cutoff,
        )
        .order_by(CreditBureauEnquiry.completed_at.desc(), CreditBureauEnquiry.requested_at.desc())
        .limit(50)
        .all()
    )
    selected_environment = "live" if str(environment).lower() in {"live", "production"} else "sandbox"
    for row in rows:
        metadata = dict(row.enquiry_data or {}).get("experian")
        metadata = dict(metadata) if isinstance(metadata, dict) else {}
        row_environment = "live" if str(metadata.get("environment") or "sandbox").lower() in {"live", "production"} else "sandbox"
        if row_environment == selected_environment:
            return row
    return None

def experian_required_for_application(
    policy: dict[str, Any],
    application: DirectLoanApplication,
    *,
    stage: str,
    amount: Decimal | None = None,
    product_id: UUID | str | None = None,
) -> bool:
    mode = str(policy.get("requirement_mode") or "optional").strip().lower()
    if mode == "optional":
        return False

    if mode == "before_affordability":
        return stage in {"affordability", "approval"}

    if stage != "approval":
        return False

    if mode == "before_approval":
        return True

    if mode == "amount_threshold":
        threshold = policy.get("required_above_amount")
        if threshold in (None, ""):
            return False
        effective_amount = Decimal(str(amount if amount is not None else application.requested_amount or 0))
        return effective_amount >= Decimal(str(threshold))

    if mode == "selected_products":
        effective_product_id = product_id or application.product_id
        if not effective_product_id:
            return False
        return str(effective_product_id) in set(policy.get("required_product_ids") or [])

    return False


def assert_experian_requirement(
    db: Session,
    *,
    application: DirectLoanApplication,
    stage: str,
    amount: Decimal | None = None,
    product_id: UUID | str | None = None,
) -> CreditBureauEnquiry | None:
    integration, policy = company_experian_policy(db, application.company_id)
    if not integration or not integration.is_enabled:
        return None

    required = experian_required_for_application(
        policy,
        application,
        stage=stage,
        amount=amount,
        product_id=product_id,
    )
    latest = latest_fresh_experian_enquiry(
        db,
        company_id=application.company_id,
        application_id=application.id,
        borrower_id=application.borrower_id,
        max_report_age_hours=int(policy["max_report_age_hours"]),
        environment=str(policy.get("environment") or "sandbox"),
    )
    if required and not latest:
        mode = str(policy.get("requirement_mode") or "optional")
        detail = {
            "before_affordability": "A fresh Experian report is required before affordability can be calculated.",
            "before_approval": "A fresh Experian report is required before this application can be approved.",
            "amount_threshold": "This loan amount requires a fresh Experian report before approval.",
            "selected_products": "The selected loan product requires a fresh Experian report before approval.",
        }.get(mode, "A fresh Experian report is required before continuing.")
        raise HTTPException(status_code=409, detail=detail)
    return latest
