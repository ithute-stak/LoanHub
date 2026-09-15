from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.access_control import LENDING_ROLES, TenantContext, assert_branch_scope, get_user_context, require_tenant_roles
from database.models.borrower import Borrower
from database.models.cdas_booking import CdasAnalysisRecord, CdasBookingOpportunity
from database.models.company_client import CompanyBorrowerAccount
from database.models.loan_product import LoanProduct
from database.models.professional_lending import DirectLoanApplication
from database.session import get_db
from services.origination_service import enforce_duplicate_policy, get_or_create_policy


router = APIRouter(prefix="/cdas-booking", tags=["CDAS Application Handoff"])


class CdasApplicationHandoffCreate(BaseModel):
    """Staff-entered origination inputs for a CDAS-sourced draft.

    CDAS values deliberately do not populate requested amount, term, pricing,
    affordability or approval fields. Those remain explicit LoanHub inputs and
    downstream origination controls.
    """

    model_config = ConfigDict(extra="forbid")

    borrower_id: UUID
    branch_id: UUID | None = None
    product_id: UUID | None = None
    requested_amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    term_count: int = Field(gt=0, le=120)
    purpose: str | None = Field(default=None, max_length=5000)
    installment_due_dates: list[date] = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_due_dates(self):
        if len(self.installment_due_dates) != self.term_count:
            raise ValueError(f"Enter exactly {self.term_count} installment due dates")
        for index in range(1, len(self.installment_due_dates)):
            if self.installment_due_dates[index] <= self.installment_due_dates[index - 1]:
                raise ValueError(f"Installment {index + 1} due date must be after installment {index}")
        return self


def _opportunity(db: Session, *, company_id: UUID, opportunity_id: UUID) -> CdasBookingOpportunity:
    item = (
        db.query(CdasBookingOpportunity)
        .filter(
            CdasBookingOpportunity.id == opportunity_id,
            CdasBookingOpportunity.company_id == company_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="CDAS opportunity not found")
    return item


def _latest_exact_analysis(
    db: Session,
    *,
    company_id: UUID,
    opportunity: CdasBookingOpportunity,
) -> CdasAnalysisRecord | None:
    """Resolve provenance conservatively; never join a name-only weak match."""
    reference = (opportunity.client_reference or "").strip()
    if reference:
        row = (
            db.query(CdasAnalysisRecord)
            .filter(
                CdasAnalysisRecord.company_id == company_id,
                CdasAnalysisRecord.client_reference == reference,
            )
            .order_by(CdasAnalysisRecord.created_at.desc())
            .first()
        )
        if row:
            return row

    profile = (opportunity.analysis_snapshot or {}).get("profile") or {}
    nid = str(profile.get("nid") or "").strip()
    employee_no = str(profile.get("employee_no") or "").strip()
    if nid:
        row = (
            db.query(CdasAnalysisRecord)
            .filter(CdasAnalysisRecord.company_id == company_id, CdasAnalysisRecord.nid == nid)
            .order_by(CdasAnalysisRecord.created_at.desc())
            .first()
        )
        if row:
            return row
    if employee_no:
        return (
            db.query(CdasAnalysisRecord)
            .filter(
                CdasAnalysisRecord.company_id == company_id,
                CdasAnalysisRecord.employee_no == employee_no,
            )
            .order_by(CdasAnalysisRecord.created_at.desc())
            .first()
        )
    return None


def _handoff_payload(opportunity: CdasBookingOpportunity, application: DirectLoanApplication | None) -> dict:
    profile = (opportunity.analysis_snapshot or {}).get("profile") or {}
    return {
        "opportunity_id": opportunity.id,
        "client_name": opportunity.client_name,
        "client_reference": opportunity.client_reference,
        "employee_no": profile.get("employee_no"),
        "nid": profile.get("nid"),
        "employer": profile.get("employer") or profile.get("employer_name"),
        "pipeline_stage": opportunity.pipeline_stage,
        "booking_open_date": opportunity.booking_open_date,
        "opportunity_agency_name": opportunity.opportunity_agency_name,
        "opportunity_expiry_date": opportunity.opportunity_expiry_date,
        "application": (
            {
                "id": application.id,
                "application_reference": application.application_reference,
                "borrower_id": application.borrower_id,
                "status": application.status,
                "requested_amount": application.requested_amount,
                "term_count": application.term_count,
                "created_at": application.created_at,
            }
            if application
            else None
        ),
    }


@router.get("/application-handoffs")
def list_application_handoffs(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    opportunities = (
        db.query(CdasBookingOpportunity)
        .filter(CdasBookingOpportunity.company_id == context.company_id)
        .order_by(CdasBookingOpportunity.created_at.desc())
        .limit(500)
        .all()
    )
    ids = [item.id for item in opportunities]
    applications = (
        db.query(DirectLoanApplication)
        .filter(
            DirectLoanApplication.company_id == context.company_id,
            DirectLoanApplication.cdas_source_opportunity_id.in_(ids),
        )
        .all()
        if ids
        else []
    )
    by_opportunity = {item.cdas_source_opportunity_id: item for item in applications}
    return {
        "items": [_handoff_payload(item, by_opportunity.get(item.id)) for item in opportunities],
        "total": len(opportunities),
        "policy_note": (
            "CDAS is source context only. Requested amount, term, affordability, pricing, approval, "
            "contracting and disbursement remain separate LoanHub origination steps."
        ),
    }


@router.post(
    "/opportunities/{opportunity_id}/application-handoff",
    status_code=status.HTTP_201_CREATED,
)
def create_application_handoff(
    opportunity_id: UUID,
    payload: CdasApplicationHandoffCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, LENDING_ROLES)
    assert_branch_scope(context, payload.branch_id or context.branch_id)
    opportunity = _opportunity(db, company_id=context.company_id, opportunity_id=opportunity_id)

    existing = (
        db.query(DirectLoanApplication)
        .filter(
            DirectLoanApplication.company_id == context.company_id,
            DirectLoanApplication.cdas_source_opportunity_id == opportunity.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"This CDAS opportunity is already linked to application {existing.application_reference}",
        )

    borrower = db.get(Borrower, payload.borrower_id)
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower not found")
    client = (
        db.query(CompanyBorrowerAccount)
        .filter(
            CompanyBorrowerAccount.company_id == context.company_id,
            CompanyBorrowerAccount.borrower_id == payload.borrower_id,
            CompanyBorrowerAccount.status == "active",
        )
        .first()
    )
    if not client:
        raise HTTPException(status_code=409, detail="The borrower must be an active company client")

    policy = get_or_create_policy(db, context.company_id, context.user.id)
    enforce_duplicate_policy(
        db,
        borrower_id=payload.borrower_id,
        company_id=context.company_id,
        policy=policy,
    )

    product = None
    if payload.product_id:
        product = (
            db.query(LoanProduct)
            .filter(
                LoanProduct.id == payload.product_id,
                LoanProduct.company_id == context.company_id,
                LoanProduct.is_active.is_(True),
            )
            .first()
        )
        if not product:
            raise HTTPException(status_code=404, detail="The selected active loan product was not found")
        requested_amount = Decimal(payload.requested_amount)
        if not (Decimal(product.min_amount) <= requested_amount <= Decimal(product.max_amount)):
            raise HTTPException(status_code=422, detail="Requested amount is outside the selected product range")
        if not (product.min_term_months <= payload.term_count <= product.max_term_months):
            raise HTTPException(status_code=422, detail="Term is outside the selected product range")

    source_analysis = _latest_exact_analysis(
        db,
        company_id=context.company_id,
        opportunity=opportunity,
    )
    now = datetime.now(timezone.utc)
    application = DirectLoanApplication(
        company_id=context.company_id,
        branch_id=payload.branch_id or client.branch_id or context.branch_id,
        borrower_id=payload.borrower_id,
        product_id=payload.product_id,
        application_reference=f"CDAS-{now:%Y%m%d}-{secrets.token_hex(4).upper()}",
        channel="cdas_booking",
        application_type="new_loan",
        requested_amount=Decimal(payload.requested_amount),
        term_count=payload.term_count,
        repayment_type="monthly",
        purpose=payload.purpose,
        preferred_payment_day=None,
        first_payment_date=payload.installment_due_dates[0],
        installment_due_dates=[value.isoformat() for value in payload.installment_due_dates],
        application_step=1,
        status="draft",
        captured_by_user_id=context.user.id,
        cdas_source_opportunity_id=opportunity.id,
        cdas_source_analysis_id=source_analysis.id if source_analysis else None,
        cdas_handoff_by_user_id=context.user.id,
        cdas_handoff_at=now,
    )
    db.add(application)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This CDAS opportunity already has a LoanHub application or the application reference collided",
        ) from exc
    db.refresh(application)
    return {
        "id": application.id,
        "application_reference": application.application_reference,
        "status": application.status,
        "borrower_id": application.borrower_id,
        "requested_amount": application.requested_amount,
        "term_count": application.term_count,
        "channel": application.channel,
        "cdas_source_opportunity_id": application.cdas_source_opportunity_id,
        "cdas_source_analysis_id": application.cdas_source_analysis_id,
        "origination_workspace_url": f"/company/origination/new?application={application.id}",
        "policy_note": (
            "Draft only. CDAS did not determine amount, term, affordability, pricing, approval or disbursement."
        ),
    }
