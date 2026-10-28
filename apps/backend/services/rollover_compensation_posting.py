"""Fail-closed transaction entry for future compensating rollover reversals.

The planned posting routine is intentionally unreachable until database-backed
concurrency, accounting and repayment-history tests certify the operation.
"""
from __future__ import annotations

from uuid import UUID
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models.loan_rollover_transfer import LoanRolloverTransfer
from database.models.loan_rollover_compensation import LoanRolloverCompensation
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus, InstallmentStatus
from database.models.repayment import RepaymentInstallment, PaymentAllocation
from database.models.payment import PaymentTransaction
from services.rollover_reversal_preflight import validate_rollover_reversal_preflight
from services.rollover_accounting_reconciliation import reconcile_rollover_accounting
from services.rollover_reversal_approval import require_rollover_reversal_approval


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

    # Fail closed unless this exact transfer has a durable checker decision.
    # The HTTP 503 at entry remains mandatory until journal certification.
    require_rollover_reversal_approval(
        db, company_id=company_id, transfer_id=transfer_id,
        maker_user_id=actor_user_id, checker_user_id=independent_approver_id,
        approval_reference=approval_reference,
    )

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

    # Reversing a facility with descendants can strand another loan or
    # invalidate a top-up/renewal chain. A specialist must reconcile it.
    linked_descendant = db.query(ClientCompanyLoan.id).filter(
        ClientCompanyLoan.company_id == company_id,
        ClientCompanyLoan.parent_loan_id == child.id,
    ).first()
    if linked_descendant is not None:
        raise HTTPException(
            status_code=409,
            detail="Child loan has a linked descendant; specialist settlement required",
        )

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
    source = db.query(RepaymentInstallment).filter(
        RepaymentInstallment.id == transfer.source_installment_id,
        RepaymentInstallment.loan_id == parent.id,
    ).with_for_update().one_or_none()
    if source is None or not source.is_superseded:
        raise HTTPException(status_code=409, detail="Original installment is not available for restoration")
    # A matching remainder alone is not sufficient: changing both total_due and
    # paid_amount by the same amount preserves the remainder but corrupts the
    # original repayment history. Require the immutable posting-time snapshot.
    if not all(key in original for key in ("installment_total_due", "installment_paid_amount")):
        raise HTTPException(status_code=409, detail="Original rollover installment evidence is missing")
    if (
        Decimal(str(source.total_due)) != Decimal(str(original["installment_total_due"]))
        or Decimal(str(source.paid_amount)) != Decimal(str(original["installment_paid_amount"]))
    ):
        raise HTTPException(status_code=409, detail="Original installment repayment history changed")
    # The source installment must still carry the original unpaid amount.
    # Do not restore a different schedule or silently double-count historical debt.
    source_remaining = Decimal(str(source.total_due)) - Decimal(str(source.paid_amount))
    if source_remaining != Decimal(str(transfer.transfer_amount)):
        raise HTTPException(
            status_code=409,
            detail="Source installment unpaid balance no longer matches rollover transfer",
        )
    if any(
        Decimal(str(getattr(source, field))) != Decimal(str(getattr(transfer, component)))
        for field, component in (
            ("principal_due", "principal_component"),
            ("interest_due", "interest_component"),
            ("fee_due", "fee_component"),
        )
    ) and Decimal(str(source.paid_amount)) == 0:
        raise HTTPException(
            status_code=409,
            detail="Source component totals no longer match the rollover ledger",
        )
    # Proposed atomic compensation. Unreachable until the entry-point 503
    # gate is deliberately removed after independent accounting certification.
    before_parent_balance, before_child_balance = parent.balance, child.balance
    amount = Decimal(str(transfer.transfer_amount))
    parent.balance = amount
    parent.status = LoanStatus.ACTIVE
    parent.is_overdue = False
    child.balance = Decimal("0")
    child.status = LoanStatus.CANCELLED
    child.is_overdue = False
    source.is_superseded = False
    source.superseded_at = None
    source.status = InstallmentStatus.PARTIALLY_PAID if Decimal(str(source.paid_amount)) > 0 else InstallmentStatus.PENDING
    child_installment = installments[0]
    child_installment.is_superseded = True
    child_installment.superseded_at = datetime.now(timezone.utc)
    snapshot = dict(parent.calculation_breakdown or {})
    snapshot["linked_rollover_compensated"] = {
        "transfer_id": str(transfer.id), "reference": reference,
        "approval_reference": approval_reference,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    parent.calculation_breakdown = snapshot
    db.add(LoanRolloverCompensation(
        company_id=company_id, transfer_id=transfer.id,
        reference=reference, approval_reference=approval_reference,
        reason=reason, amount=amount,
        principal_component=transfer.principal_component,
        interest_component=transfer.interest_component,
        fee_component=transfer.fee_component,
        approved_by_user_id=independent_approver_id,
        evidence={"actor_user_id": str(actor_user_id), "no_cash_movement": True},
    ))
    db.flush()
    if Decimal(str(parent.balance)) + Decimal(str(child.balance)) != amount:
        raise HTTPException(status_code=409, detail="Compensation would change total receivables")
    reconcile_rollover_accounting(
        transfer=transfer, company_id=company_id,
        parent_before=before_child_balance, parent_after=child.balance,
        child_before=before_parent_balance, child_after=parent.balance,
    )
    db.commit()
    return {"transfer_id": str(transfer.id), "compensation_reference": reference,
            "parent_balance": str(parent.balance), "child_balance": str(child.balance)}

