"""Controlled carry-forward of an installment shortfall without creating or extinguishing debt."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from database.config.config import settings
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models.audit_log import AuditLog
from database.models.enums import InstallmentStatus, LoanStatus
from database.models.repayment import RepaymentInstallment

CENT = Decimal("0.01")


def cents(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def carry_installment_shortfall(
    db: Session, *, loan, installment_id, actor_user_id, actor_role: str,
    reason: str, agreement_reference: str | None = None,
):
    """Post an approved same-loan due-date rollover, keeping the loan total unchanged.

    The first installment becomes contractually satisfied *via an authorized*
    rollover, not by inventing a payment. The unpaid components move to the
    next installment. No interest or fee is created.
    """
    if loan.status not in (LoanStatus.ACTIVE, LoanStatus.DEFAULTED):
        raise HTTPException(status_code=409, detail="Only active loans can have arrears rolled forward")
    if len(reason.strip()) < 12:
        raise HTTPException(status_code=422, detail="An approval reason of at least 12 characters is required")
    rows = sorted((i for i in loan.installments if not i.is_superseded), key=lambda i: i.installment_number)
    current = next((i for i in rows if i.id == installment_id), None)
    if current is None:
        raise HTTPException(status_code=404, detail="Active installment not found on this loan")
    if current.status == InstallmentStatus.WAIVED:
        raise HTTPException(status_code=409, detail="Waived installments cannot be carried forward")
    if not current.paid_amount or cents(current.paid_amount) <= 0:
        raise HTTPException(status_code=409, detail="Only partially paid installments qualify")
    remaining = cents(current.total_due) - cents(current.paid_amount)
    if remaining <= 0:
        raise HTTPException(status_code=409, detail="There is no remaining amount to carry")
    next_row = next((i for i in rows if i.installment_number > current.installment_number), None)
    if next_row is None:
        raise HTTPException(
            status_code=409,
            detail="Final-installment shortfalls require a separately approved linked rollover facility; no automatic new loan may be created",
        )
    if next_row.status in (InstallmentStatus.PAID, InstallmentStatus.WAIVED):
        raise HTTPException(status_code=409, detail="The next installment is already settled or waived")

    components = [cents(current.principal_due), cents(current.interest_due), cents(current.fee_due)]
    if sum(components) != cents(current.total_due):
        raise HTTPException(status_code=409, detail="Installment component totals require reconciliation")
    # Transfer outstanding interest and fees first, then principal. This only
    # reassigns due components; there is no new interest, cash or principal.
    transferred = [Decimal("0.00")] * 3
    available = remaining
    for index in (2, 1, 0):
        transferred[index] = min(components[index], available)
        available -= transferred[index]
    if available:
        raise HTTPException(status_code=409, detail="Shortfall component allocation failed")
    before = {
        "from_due": str(cents(current.total_due)),
        "to_due": str(cents(next_row.total_due)),
        "from_status": current.status.value,
        "to_status": next_row.status.value,
    }
    for field, part in zip(("principal_due", "interest_due", "fee_due"), transferred):
        setattr(current, field, cents(getattr(current, field)) - part)
        setattr(next_row, field, cents(getattr(next_row, field)) + part)
    current.total_due = cents(current.total_due) - remaining
    next_row.total_due = cents(next_row.total_due) + remaining
    current.status = InstallmentStatus.PAID
    current.paid_at = datetime.now(timezone.utc)
    loan.is_overdue = any(
        i.due_date < datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date() and cents(i.total_due) > cents(i.paid_amount)
        and i.status != InstallmentStatus.WAIVED for i in rows
    )
    history = list((loan.calculation_breakdown or {}).get("installment_carry_forward_history") or [])
    history.append({
        "from_installment_id": str(current.id), "to_installment_id": str(next_row.id),
        "amount": str(remaining), "approved_by": str(actor_user_id),
        "reason": reason.strip(), "agreement_reference": agreement_reference,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    })
    loan.calculation_breakdown = {**(loan.calculation_breakdown or {}), "installment_carry_forward_history": history}
    db.add(AuditLog(
        user_id=actor_user_id, company_id=loan.company_id, branch_id=loan.branch_id,
        action="loan.installment_arrears_carried_forward",
        table_name="repayment_installments", entity_type="repayment_installment",
        record_id=current.id, description=f"Transferred {remaining} unpaid from installment {current.installment_number} to {next_row.installment_number}",
        actor_role=actor_role, severity="info", status="success",
        before_data=before,
        after_data={"from_due": str(current.total_due), "to_due": str(next_row.total_due)},
        changed_fields=["total_due", "principal_due", "interest_due", "fee_due", "status"],
        event_data={"loan_id": str(loan.id), "amount": str(remaining), "reason": reason.strip(), "agreement_reference": agreement_reference},
    ))
    db.commit()
    return {
        "from_installment": current.installment_number,
        "to_installment": next_row.installment_number,
        "carried_amount": str(remaining),
        "next_total_due": str(next_row.total_due),
        "loan_balance": str(loan.balance),
    }
