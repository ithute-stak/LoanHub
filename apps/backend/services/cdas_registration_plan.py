from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.cdas_booking import CdasBookingOpportunity
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus, RepaymentType
from database.models.lending_operations import CDASPayrollProfile
from services.cdas_deduction_lifecycle import CdasLifecycleError, get_official_mandate_for_loan
from services.cdas_exact_identity import CdasExactIdentityError, require_exact_verified_payroll_profile


_MONEY = Decimal("0.01")


def _money(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(_MONEY)
    except Exception:
        return Decimal("0.00")


def _current_effective_month() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def _latest_daily_snapshot(
    db: Session,
    *,
    company_id: UUID,
    borrower_id: UUID,
) -> dict[str, Any] | None:
    row = (
        db.query(CdasBookingOpportunity)
        .filter(
            CdasBookingOpportunity.company_id == company_id,
            CdasBookingOpportunity.client_reference == f"borrower:{borrower_id}",
        )
        .order_by(CdasBookingOpportunity.updated_at.desc(), CdasBookingOpportunity.created_at.desc())
        .first()
    )
    if row is None or not isinstance(row.analysis_snapshot, dict):
        return None
    snapshot = dict(row.analysis_snapshot)
    if str(snapshot.get("source") or "") != "CDAS_DAILY_INTELLIGENCE":
        return None
    return snapshot


def build_cdas_registration_plan(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID | None,
    loan_id: UUID,
) -> dict[str, Any]:
    """Prepare, but never execute, an official CDAS registration.

    The contractual installment/principal/term always come from LoanHub. Daily
    CDAS intelligence is advisory readiness evidence only; the actual registration
    endpoint still refreshes live affordability, exact identity and borrower consent
    immediately before any provider write.
    """
    loan = (
        db.query(ClientCompanyLoan)
        .filter(
            ClientCompanyLoan.id == loan_id,
            ClientCompanyLoan.company_id == company_id,
        )
        .one_or_none()
    )
    if loan is None:
        raise CdasLifecycleError(404, "Loan was not found for this company")
    if branch_id and loan.branch_id != branch_id:
        raise CdasLifecycleError(403, "The selected loan is outside the active branch")

    blockers: list[str] = []
    if loan.status not in {LoanStatus.APPROVED, LoanStatus.ACTIVE}:
        blockers.append("LoanHub loan must be approved or active before CDAS registration.")
    if loan.repayment_type != RepaymentType.MONTHLY:
        blockers.append("CDAS payroll registration requires a monthly LoanHub repayment schedule.")

    profile = (
        db.query(CDASPayrollProfile)
        .filter(
            CDASPayrollProfile.company_id == company_id,
            CDASPayrollProfile.borrower_id == loan.borrower_id,
        )
        .one_or_none()
    )
    exact_profile: CDASPayrollProfile | None = None
    if profile is None:
        blockers.append("Verify this borrower by exact National ID before preparing a CDAS deduction.")
    else:
        try:
            exact_profile = require_exact_verified_payroll_profile(
                profile,
                requested_employee_no=profile.employee_number,
            )
        except CdasExactIdentityError as exc:
            blockers.append(exc.message)

    existing = get_official_mandate_for_loan(db, company_id=company_id, loan_id=loan_id)
    if existing is not None:
        blockers.append("This LoanHub loan already has an official CDAS mandate.")

    snapshot = _latest_daily_snapshot(
        db,
        company_id=company_id,
        borrower_id=loan.borrower_id,
    )
    latest_affordability = _money(snapshot.get("available_affordability")) if snapshot else None
    suggested = _money(snapshot.get("suggested_monthly_deduction")) if snapshot else None
    estimated_months = snapshot.get("estimated_collection_months") if snapshot else None
    monitored_on = snapshot.get("local_date") if snapshot else None

    contractual_installment = _money(loan.installment_amount)
    if snapshot is None:
        blockers.append("No daily CDAS affordability result is available yet for this borrower.")
    elif latest_affordability is not None and latest_affordability < contractual_installment:
        blockers.append("The latest monitored CDAS affordability is below the contractual LoanHub installment.")

    return {
        "ready": len(blockers) == 0,
        "blockers": blockers,
        "loan_id": str(loan.id),
        "loan_reference": loan.loan_reference,
        "borrower_id": str(loan.borrower_id),
        "employee_no": exact_profile.employee_number if exact_profile else None,
        "deduction_amount": float(contractual_installment),
        "principal_amount": float(_money(loan.principal_amount)),
        "total_installment": int(loan.repayment_period or 0),
        "effective_month": _current_effective_month(),
        "latest_affordability": float(latest_affordability) if latest_affordability is not None else None,
        "daily_suggested_monthly_deduction": float(suggested) if suggested is not None else None,
        "daily_estimated_collection_months": int(estimated_months) if estimated_months not in (None, "") else None,
        "latest_monitor_date": monitored_on,
        "existing_mandate": existing is not None,
        "borrower_consent_required": True,
        "item_code_required": True,
        "reference_no_required": True,
        "provider_write_performed": False,
        "message": (
            "Ready to prefill. Registration will still refresh exact identity and live affordability, require borrower consent, and use the official single-shot CDAS write path."
            if len(blockers) == 0
            else "Preparation found items that must be resolved before official CDAS registration."
        ),
    }
