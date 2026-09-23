from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_CEILING
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context, require_tenant_roles
from database.config.config import settings
from database.models.cdas_booking import CdasBookingOpportunity
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus, UserRole
from database.models.lending_operations import CDASPayrollProfile
from database.session import get_db


router = APIRouter(prefix="/cdas/daily-intelligence", tags=["CDAS Daily Intelligence"])

_HEALTH_ROLES = {UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN}
_REGISTRATION_DRAFT_ROLES = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.BRANCH_MANAGER,
    UserRole.LOAN_OFFICER,
}
_ELIGIBLE_LOAN_STATUSES = {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}


def _require_company(context: TenantContext) -> UUID:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")
    return context.company_id


def _money(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def _local_today() -> date:
    from datetime import datetime

    return datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date()


def _next_month(value: date) -> str:
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    return f"{year:04d}-{month:02d}"


@router.get("/status")
def get_daily_cdas_intelligence_status(
    days: int = Query(default=7, ge=1, le=31),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Summarize recent 03:45 CDAS monitoring outcomes from durable opportunity snapshots."""
    company_id = _require_company(context)
    require_tenant_roles(context, _HEALTH_ROLES)

    rows = (
        db.query(CdasBookingOpportunity)
        .filter(CdasBookingOpportunity.company_id == company_id)
        .all()
    )
    today = _local_today()
    cutoff = date.fromordinal(today.toordinal() - (days - 1))

    by_date: dict[str, dict[str, int]] = {}
    latest_success_date: str | None = None
    latest_check_date: str | None = None
    for row in rows:
        snapshot = dict(row.analysis_snapshot or {})
        if snapshot.get("source") != "CDAS_DAILY_INTELLIGENCE":
            continue
        raw_date = snapshot.get("last_check_date") or snapshot.get("local_date")
        try:
            checked_date = date.fromisoformat(str(raw_date))
        except Exception:
            continue
        if checked_date < cutoff or checked_date > today:
            continue
        key = checked_date.isoformat()
        counters = by_date.setdefault(
            key,
            {"checked": 0, "ready": 0, "no_capacity": 0, "failed": 0},
        )
        counters["checked"] += 1
        status = str(snapshot.get("last_check_status") or "success").lower()
        action = str(snapshot.get("recommended_action") or "")
        if status == "failed":
            counters["failed"] += 1
        elif action == "READY_FOR_COLLECTION_REVIEW":
            counters["ready"] += 1
        elif action == "MONITOR_NO_CAPACITY":
            counters["no_capacity"] += 1
        if latest_check_date is None or key > latest_check_date:
            latest_check_date = key
        if status == "success" and (latest_success_date is None or key > latest_success_date):
            latest_success_date = key

    today_counts = by_date.get(
        today.isoformat(),
        {"checked": 0, "ready": 0, "no_capacity": 0, "failed": 0},
    )
    if today_counts["checked"] == 0:
        overall = "PENDING_OR_NO_ELIGIBLE_PROFILES"
    elif today_counts["failed"] > 0:
        overall = "DEGRADED"
    else:
        overall = "HEALTHY"

    return {
        "date": today.isoformat(),
        "timezone": settings.APP_TIMEZONE,
        "scheduled_time": "03:45",
        "status": overall,
        "today": today_counts,
        "latest_check_date": latest_check_date,
        "latest_success_date": latest_success_date,
        "history": [
            {"date": key, **by_date[key]}
            for key in sorted(by_date.keys(), reverse=True)
        ],
        "provider_writes": 0,
    }


@router.get("/opportunities/{opportunity_id}/registration-draft")
def get_registration_draft(
    opportunity_id: UUID,
    loan_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Build a server-validated CDAS registration draft for a ready exact-ID case.

    This endpoint never writes to CDAS. It re-validates the exact-ID payroll link,
    the current LoanHub loan balance and the freshness of the daily affordability
    result before returning values that the operator can review and submit through
    the existing crash-safe registration endpoint.
    """
    company_id = _require_company(context)
    require_tenant_roles(context, _REGISTRATION_DRAFT_ROLES)

    opportunity = (
        db.query(CdasBookingOpportunity)
        .filter(
            CdasBookingOpportunity.id == opportunity_id,
            CdasBookingOpportunity.company_id == company_id,
        )
        .one_or_none()
    )
    if opportunity is None:
        raise HTTPException(status_code=404, detail="CDAS opportunity not found")

    snapshot = dict(opportunity.analysis_snapshot or {})
    if snapshot.get("source") != "CDAS_DAILY_INTELLIGENCE":
        raise HTTPException(status_code=409, detail="This opportunity is not backed by daily CDAS intelligence")
    if snapshot.get("identity_policy") != "EXACT_NATIONAL_ID_VERIFIED_PROFILE_ONLY":
        raise HTTPException(status_code=409, detail="Exact National ID verification is required")
    if str(snapshot.get("last_check_status") or "success").lower() != "success":
        raise HTTPException(status_code=409, detail="The latest CDAS check did not succeed")
    if snapshot.get("recommended_action") != "READY_FOR_COLLECTION_REVIEW":
        raise HTTPException(status_code=409, detail="This opportunity is not ready for collection review")

    raw_check_date = snapshot.get("last_check_date") or snapshot.get("local_date")
    if str(raw_check_date or "") != _local_today().isoformat():
        raise HTTPException(status_code=409, detail="A fresh same-day CDAS affordability check is required")

    try:
        borrower_id = UUID(str(snapshot.get("borrower_id")))
    except Exception as exc:
        raise HTTPException(status_code=409, detail="The opportunity does not contain a valid borrower link") from exc

    profile = (
        db.query(CDASPayrollProfile)
        .filter(
            CDASPayrollProfile.company_id == company_id,
            CDASPayrollProfile.borrower_id == borrower_id,
            CDASPayrollProfile.verified.is_(True),
        )
        .one_or_none()
    )
    if profile is None:
        raise HTTPException(status_code=409, detail="The exact-ID CDAS payroll link is no longer verified")
    if str(snapshot.get("employee_no") or "") != str(profile.employee_number):
        raise HTTPException(status_code=409, detail="The CDAS employee link changed after the daily check")

    loan = (
        db.query(ClientCompanyLoan)
        .filter(
            ClientCompanyLoan.id == loan_id,
            ClientCompanyLoan.company_id == company_id,
            ClientCompanyLoan.borrower_id == borrower_id,
            ClientCompanyLoan.status.in_(_ELIGIBLE_LOAN_STATUSES),
            ClientCompanyLoan.balance > 0,
        )
        .one_or_none()
    )
    if loan is None:
        raise HTTPException(status_code=409, detail="The selected LoanHub loan is not eligible for CDAS collection")
    if context.branch_id and loan.branch_id != context.branch_id:
        raise HTTPException(status_code=403, detail="The selected loan is outside the active branch")

    affordability = max(_money(snapshot.get("available_affordability")), Decimal("0.00"))
    outstanding = max(_money(loan.balance), Decimal("0.00"))
    deduction = min(affordability, outstanding)
    if deduction <= 0 or outstanding <= 0:
        raise HTTPException(status_code=409, detail="No positive same-day CDAS collection capacity is available")

    installments = int((outstanding / deduction).to_integral_value(rounding=ROUND_CEILING))
    if installments > 600:
        raise HTTPException(status_code=409, detail="The calculated CDAS collection term exceeds the 600-installment safety limit")

    return {
        "opportunity_id": str(opportunity.id),
        "loan_id": str(loan.id),
        "loan_reference": loan.loan_reference,
        "borrower_id": str(borrower_id),
        "employee_no": profile.employee_number,
        "identity_verified": True,
        "identity_policy": "EXACT_NATIONAL_ID_VERIFIED_PROFILE_ONLY",
        "affordability_checked_on": str(raw_check_date),
        "available_affordability": float(affordability),
        "current_outstanding": float(outstanding),
        "suggested_deduction_amount": float(deduction),
        "suggested_total_installments": installments,
        "suggested_effective_month": _next_month(_local_today()),
        "suggested_reference_no": loan.loan_reference,
        "borrower_consent_required": True,
        "ready_to_submit": False,
        "required_operator_fields": ["item_code", "loan_policy", "borrower_consent"],
        "submission_endpoint": "/api/v1/cdas/loan-deductions",
        "provider_write_performed": False,
    }
