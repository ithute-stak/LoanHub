from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models.audit_log import AuditLog
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import InstallmentStatus, LoanStatus, UserRole
from database.models.repayment import RepaymentInstallment


EDITABLE_LOAN_STATUSES = {
    LoanStatus.APPROVED,
    LoanStatus.ACTIVE,
    LoanStatus.DEFAULTED,
}
LOCKED_INSTALLMENT_STATUSES = {
    InstallmentStatus.PAID,
    InstallmentStatus.WAIVED,
}


def adjust_installment_due_date(
    db: Session,
    *,
    loan: ClientCompanyLoan,
    installment_id: UUID,
    new_due_date: date,
    agreement_note: str,
    agreement_reference: str | None,
    actor_user_id: UUID,
    actor_role: UserRole | str,
) -> RepaymentInstallment:
    """Move one unpaid installment to a later agreed date without changing approved financial amounts.

    This is an administrative rescheduling action. Principal, interest, fees and
    total due remain exactly as approved. A separate financial restructure flow
    should be used when an extension also changes pricing.
    """
    if loan.status not in EDITABLE_LOAN_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Installment due dates can only be extended on approved, active, or defaulted loans",
        )

    installments = sorted(loan.installments, key=lambda item: item.installment_number)
    installment = next((item for item in installments if item.id == installment_id), None)
    if installment is None:
        raise HTTPException(status_code=404, detail="Installment not found on this loan")

    if installment.status in LOCKED_INSTALLMENT_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="A paid or waived installment due date cannot be changed",
        )

    old_due_date = installment.due_date
    if new_due_date <= old_due_date:
        raise HTTPException(
            status_code=422,
            detail="The new due date must be later than the current due date",
        )

    next_installment = next(
        (item for item in installments if item.installment_number > installment.installment_number),
        None,
    )
    if next_installment is not None and new_due_date >= next_installment.due_date:
        raise HTTPException(
            status_code=409,
            detail=(
                f"The new due date must remain before installment "
                f"{next_installment.installment_number} due on {next_installment.due_date.isoformat()}. "
                "Extend the following installment first when a longer reschedule is required."
            ),
        )

    note = agreement_note.strip()
    if len(note) < 3:
        raise HTTPException(status_code=422, detail="Enter the agreement/reason for the extension")
    reference = agreement_reference.strip() if agreement_reference else None

    installment.due_date = new_due_date

    if installment.installment_number == installments[0].installment_number:
        loan.first_payment_due = new_due_date
    if installment.installment_number == installments[-1].installment_number:
        loan.maturity_date = new_due_date

    if installment.status == InstallmentStatus.OVERDUE and new_due_date >= date.today():
        installment.status = (
            InstallmentStatus.PARTIALLY_PAID
            if Decimal(installment.paid_amount or 0) > 0
            else InstallmentStatus.PENDING
        )
    loan.is_overdue = any(item.status == InstallmentStatus.OVERDUE for item in installments)

    role_value = actor_role.value if isinstance(actor_role, UserRole) else str(actor_role)
    db.add(
        AuditLog(
            user_id=actor_user_id,
            company_id=loan.company_id,
            branch_id=loan.branch_id,
            action="loan.installment_due_date_adjusted",
            table_name="repayment_installments",
            entity_type="repayment_installment",
            record_id=installment.id,
            description=(
                f"Installment {installment.installment_number} due date adjusted "
                f"from {old_due_date.isoformat()} to {new_due_date.isoformat()}"
            ),
            actor_role=role_value,
            severity="info",
            status="success",
            before_data={"due_date": old_due_date.isoformat()},
            after_data={"due_date": new_due_date.isoformat()},
            changed_fields=["due_date"],
            event_data={
                "loan_id": str(loan.id),
                "loan_reference": loan.loan_reference,
                "installment_number": installment.installment_number,
                "agreement_note": note,
                "agreement_reference": reference,
                "financial_amounts_changed": False,
                "change_type": "extension",
            },
        )
    )
    db.commit()
    return installment


def extend_installment_due_date(
    db: Session,
    *,
    loan: ClientCompanyLoan,
    installment_id: UUID,
    new_due_date: date,
    agreement_note: str,
    agreement_reference: str | None,
    actor_user_id: UUID,
    actor_role: UserRole | str,
) -> RepaymentInstallment:
    """Backward-compatible alias for the agreed installment date adjustment flow.

    Older LoanHub callers and regression tests used ``extend_installment_due_date``.
    The service was later renamed to ``adjust_installment_due_date`` to better
    describe the action. Keep both names mapped to the same implementation so
    route/test compatibility does not depend on the rename.
    """
    return adjust_installment_due_date(
        db,
        loan=loan,
        installment_id=installment_id,
        new_due_date=new_due_date,
        agreement_note=agreement_note,
        agreement_reference=agreement_reference,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
    )
