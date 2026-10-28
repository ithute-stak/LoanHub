"""Fail-closed transaction entry for future compensating rollover reversals.

The planned posting routine is intentionally unreachable until database-backed
concurrency, accounting and repayment-history tests certify the operation.
"""
from __future__ import annotations

from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models.loan_rollover_transfer import LoanRolloverTransfer
from database.models.loan_rollover_compensation import LoanRolloverCompensation
from database.models.client_loan_company import ClientCompanyLoan
from database.models.repayment import RepaymentInstallment, PaymentAllocation
from database.models.payment import PaymentTransaction
from services.rollover_reversal_preflight import validate_rollover_reversal_preflight


def post_rollover_compensation(
    db: Session, *, company_id: UUID, transfer_id: UUID, actor_user_id: UUID,
    independent_approver_id: UUID, reference: str, approval_reference: str,
    reason: str,
) -> dict:
    # Critical: do not remove until real-mapped PostgreSQL transactional tests,
    # immutable finance journal entries and maker-checker authorization pass.
    raise HTTPException(
        status_code=503,
        detail="Compensating rollover reversal is disabled pending accounting certification",
    )

    if actor_user_id == independent_approver_id:
        raise HTTPException(status_code=409, detail="Independent approval is required")
    if not reference.strip() or not approval_reference.strip() or not reason.strip():
        raise HTTPException(status_code=422, detail="Reversal references and reason are required")

    transfer = db.query(LoanRolloverTransfer).filter(
        LoanRolloverTransfer.id == transfer_id,
        LoanRolloverTransfer.company_id == company_id,
    ).with_for_update().one_or_none()
    if transfer is None:
        raise HTTPException(status_code=404, detail="Rollover transfer not found")
    if db.query(LoanRolloverCompensation.id).filter(
        LoanRolloverCompensation.transfer_id == transfer.id
    ).first():
        raise HTTPException(status_code=409, detail="Rollover already compensated")
    parent = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.id == transfer.parent_loan_id,
        ClientCompanyLoan.company_id == company_id,
    ).with_for_update().one_or_none()
    child = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.id == transfer.child_loan_id,
        ClientCompanyLoan.company_id == company_id,
    ).with_for_update().one_or_none()
    if parent is None or child is None:
        raise HTTPException(status_code=409, detail="Linked loans are missing")

    installments = db.query(RepaymentInstallment).filter(
        RepaymentInstallment.loan_id == child.id
    ).with_for_update().all()

    # Every recorded payment or allocation is treated as activity, regardless
    # of status or amount. A reversal must not erase provider-side history.
    child_payment_count = db.query(PaymentTransaction.id).filter(
        PaymentTransaction.company_id == company_id,
        PaymentTransaction.loan_id == child.id,
    ).count()
    allocation_count = db.query(PaymentAllocation.payment_id).join(
        RepaymentInstallment,
        PaymentAllocation.installment_id == RepaymentInstallment.id,
    ).filter(RepaymentInstallment.loan_id == child.id).count()
    validate_rollover_reversal_preflight(
        transfer=transfer, parent=parent, child=child,
        child_installments=installments,
        child_payments_count=child_payment_count + allocation_count,
        actor_company_id=company_id,
    )
    from services.rollover_compensation_balances import prepare_rollover_compensation_balances
    original = ((parent.calculation_breakdown or {}).get("linked_rollover_out") or {}).get("original") or {}
    prepare_rollover_compensation_balances(
        transfer_amount=transfer.transfer_amount,
        parent_balance=parent.balance,
        child_balance=child.balance,
        child_amount_paid=child.amount_paid,
        original_parent_balance=original.get("balance", "-1"),
    )
    raise HTTPException(status_code=503, detail="Financial reversal posting remains disabled")
