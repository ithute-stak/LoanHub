"""Atomically transfer the last installment remainder to an inherited child facility.

An existing receivable is *reassigned*, never repaid or disbursed. The immutable
payment allocations remain attached to the parent. The loan/child linkage and
audit log form the transactional transfer record; a dedicated reversal workflow
must be added before reversals are allowed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models.audit_log import AuditLog
from database.models.loan_rollover_transfer import LoanRolloverTransfer
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import InstallmentStatus, LoanStatus
from database.models.repayment import RepaymentInstallment
from services.linked_rollover_transfer_plan import prepare_linked_rollover
from services.rollover_receivable_reconciliation import validate_rollover_receivable_transfer
from services.loan_service import generate_loan_reference
from services.rollover_component_evidence import verify_component_allocation_evidence
from services.rollover_accounting_reconciliation import reconcile_rollover_accounting

def split_rollover_components(*, principal, interest, fees, total_due, paid_amount):
    """Allocate historical payments to principal first; preserve unpaid charge types.

    This policy must match LoanHub's authoritative repayment-allocation waterfall
    before posting is enabled. It is isolated for financial review and testing.
    """
    values = [Decimal(str(v or 0)) for v in (principal, interest, fees)]
    full = Decimal(str(total_due))
    unpaid = full - Decimal(str(paid_amount))
    if full != sum(values) or unpaid <= 0 or any(v < 0 for v in values):
        raise HTTPException(status_code=409, detail="Source installment components do not reconcile")
    # The repayment allocation table records only installment-level amounts,
    # not principal/interest/fee allocation. For mixed-component partial
    # payments, no valid residual classification can be inferred from totals.
    if Decimal(str(paid_amount)) > 0 and sum(v > 0 for v in values) > 1:
        raise HTTPException(
            status_code=409,
            detail="Mixed principal/interest/fee partial repayment requires an authoritative component allocation ledger",
        )
    remaining = unpaid
    result = [Decimal("0"), Decimal("0"), Decimal("0")]
    for idx in (2, 1, 0):
        result[idx] = min(remaining, values[idx])
        remaining -= result[idx]
    if remaining:
        raise HTTPException(status_code=409, detail="Transferred components do not reconcile")
    return tuple(result)


def post_final_rollover(
    db: Session, *, company_id: UUID, parent_id: UUID, installment_id: UUID,
    approved_amount: Decimal, due_date, agreement_reference: str,
    approval_reference: str, actor_user_id: UUID, actor_role: str, as_of,
    component_evidence: dict | None = None,
) -> dict:
    # Defense in depth: this unfinished financial operation must not be callable
    # from another internal service while the HTTP route is disabled.
    raise HTTPException(
        status_code=503,
        detail="Final rollover posting is disabled until PostgreSQL and accounting certification",
    )
    # Lock the parent before reading children/schedules, serializing concurrent
    # posting requests. The parent lock is always acquired before any writes.
    parent = (
        db.query(ClientCompanyLoan)
        .filter(ClientCompanyLoan.id == parent_id, ClientCompanyLoan.company_id == company_id)
        .with_for_update()
        .one_or_none()
    )
    if parent is None:
        raise HTTPException(status_code=404, detail="Parent loan not found")
    children = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.company_id == company_id,
        ClientCompanyLoan.parent_loan_id == parent_id,
    ).all()
    if children:
        raise HTTPException(status_code=409, detail="A linked facility already exists for this parent loan")
    # Prevent an unapproved second-generation linked rollover, or transferring
    # a loan carrying active payroll deductions without mandate migration.
    if parent.parent_loan_id is not None:
        raise HTTPException(status_code=409, detail="Chained rollover facilities require manual reconciliation")
    if parent.cdas_collection_enabled:
        raise HTTPException(status_code=409, detail="Active CDAS collection must be migrated and approved before rollover")
    if (parent.calculation_breakdown or {}).get("linked_rollover_out"):
        raise HTTPException(status_code=409, detail="This loan has already been transferred")
    plan = prepare_linked_rollover(
        parent, installment_id, approved_amount=approved_amount,
        effective_due_date=due_date, agreement_reference=agreement_reference,
        approval_reference=approval_reference, as_of=as_of,
    )
    validate_rollover_receivable_transfer(plan=plan, parent_outstanding=parent.balance)
    row = next(i for i in parent.installments if i.id == installment_id)
    outstanding = Decimal(plan["approved_transfer_amount"])
    # Preserve the principal / earned-interest / fee distinction.
    # Do not transform outstanding charges into new loan principal.
    # The original payment ledger does not establish the component waterfall.
    # Require independently verified evidence for mixed-component schedules.
    component_count = sum(
        Decimal(str(value or 0)) > 0
        for value in (row.principal_due, row.interest_due, row.fee_due)
    )
    if component_count > 1:
        verified = verify_component_allocation_evidence(
            installment=row, evidence=component_evidence,
        )
        carried_principal = Decimal(verified["remaining_principal"])
        carried_interest = Decimal(verified["remaining_interest"])
        carried_fees = Decimal(verified["remaining_fees"])
    else:
        carried_principal, carried_interest, carried_fees = split_rollover_components(
            principal=row.principal_due, interest=row.interest_due, fees=row.fee_due,
            total_due=row.total_due, paid_amount=row.paid_amount,
        )
    if sum((carried_principal, carried_interest, carried_fees)) != outstanding:
        raise HTTPException(status_code=409, detail="Component balance differs from approved transfer")
    # The transfer may only close the one remaining open installment. Paid
    # historic installments remain in the active historical schedule.
    open_rows = [
        i for i in parent.installments
        if not i.is_superseded
        and Decimal(str(i.total_due or 0)) > Decimal(str(i.paid_amount or 0))
        and i.status != InstallmentStatus.WAIVED
    ]
    if len(open_rows) != 1 or open_rows[0].id != row.id:
        raise HTTPException(status_code=409, detail="Other open installments require reconciliation")
    original = {
        "balance": str(parent.balance),
        "total_repayable": str(parent.total_repayable),
        "installment_total_due": str(row.total_due),
        "installment_paid_amount": str(row.paid_amount),
        "installment_status": row.status.value,
        "original_interest_rate": str(parent.interest_rate),
    }
    now = datetime.now(timezone.utc)
    child = ClientCompanyLoan(
        company_id=parent.company_id, branch_id=parent.branch_id,
        borrower_id=parent.borrower_id, parent_loan_id=parent.id,
        loan_reference=generate_loan_reference(db, parent.company),
        origination_channel="balance_rollover",
        is_top_up=False, principal_amount=carried_principal,
        interest_rate=Decimal("0"), processing_fee=Decimal("0"),
        total_repayable=outstanding,
        repayment_type=parent.repayment_type, repayment_period=1,
        installment_amount=outstanding, calculation_method=parent.calculation_method,
        calculation_breakdown={
            "linked_rollover": {
                "parent_loan_id": str(parent.id), "source_installment_id": str(row.id),
                "signed_agreement": agreement_reference,
                "credit_approval": approval_reference, "transferred_amount": str(outstanding),
                "transferred_components": {"principal": str(carried_principal), "interest": str(carried_interest), "fees": str(carried_fees)},
                "parent_terms": {
                    "interest_rate": str(parent.interest_rate),
                    "repayment_type": parent.repayment_type.value,
                    "calculation_method": parent.calculation_method,
                    "cdas_collection_enabled": bool(parent.cdas_collection_enabled),
                },
                "effective_at": now.isoformat(), "no_cash_disbursement": True,
                "no_new_interest_or_fees": True,
            },
            "schedule_rows": [{
                "installment_number": 1, "due_date": due_date.isoformat(),
                "principal_due": str(carried_principal), "interest_due": str(carried_interest),
                "fee_due": str(carried_fees), "total_due": str(outstanding),
            }],
        },
        cdas_collection_enabled=False, cdas_collection_plan={},
        approved_at=now, approved_by_user_id=actor_user_id,
        first_payment_due=due_date, preferred_payment_day=parent.preferred_payment_day,
        maturity_date=due_date, amount_paid=Decimal("0"),
        balance=outstanding, status=LoanStatus.ACTIVE,
        risk_level=parent.risk_level, is_overdue=False,
        automatic_renewal_enabled=False,
    )
    db.add(child)
    db.flush()  # Allocates distinct folio through existing loan before_insert hook.
    db.add(RepaymentInstallment(
        loan_id=child.id, installment_number=1, due_date=due_date,
        principal_due=carried_principal, interest_due=carried_interest,
        fee_due=carried_fees, total_due=outstanding, paid_amount=Decimal("0"),
        status=InstallmentStatus.PENDING,
    ))
    # Historical allocations and installment components remain untouched; the
    # superseded final installment stays visible for audits, but cannot collect.
    row.is_superseded = True
    row.superseded_at = now
    parent.balance = Decimal("0")
    # Preserve original contractual total; the transfer is separately tracked.
    parent.status = LoanStatus.COMPLETED
    parent.is_overdue = False
    previous = dict(parent.calculation_breakdown or {})
    previous["linked_rollover_out"] = {
        "child_loan_id": str(child.id), "amount": str(outstanding),
        "approved_by": str(actor_user_id), "signed_agreement": agreement_reference,
        "approval_reference": approval_reference, "posted_at": now.isoformat(),
        "original": original,
    }
    parent.calculation_breakdown = previous
    # Record the receivable transfer in the same SQL transaction as the
    # loan changes. Both API and service posting gates remain disabled.
    transfer_record = LoanRolloverTransfer(
        company_id=parent.company_id, parent_loan_id=parent.id,
        child_loan_id=child.id, source_installment_id=row.id,
        transfer_reference=approval_reference,
        agreement_reference=agreement_reference,
        approval_reference=approval_reference,
        principal_component=carried_principal,
        interest_component=carried_interest, fee_component=carried_fees,
        transfer_amount=outstanding, status="posted",
        posted_by_user_id=actor_user_id,
        evidence={
            "original": original,
            "approved_transfer_amount": str(outstanding),
            "allocation_evidence": component_evidence if component_count > 1 else None,
            "no_cash_movement": True,
            "recorded_at": now.isoformat(),
        },
    )
    db.add(transfer_record)
    db.add(AuditLog(
        user_id=actor_user_id, company_id=parent.company_id, branch_id=parent.branch_id,
        action="loan.final_installment_receivable_transferred", table_name="client_company_loan",
        entity_type="client_company_loan", record_id=parent.id,
        actor_role=actor_role, severity="info", status="success",
        description=f"Transferred {outstanding} outstanding receivable from {parent.loan_reference} to {child.loan_reference}; no cash disbursed",
        before_data=original,
        after_data={"parent_balance": "0.00", "child_loan_id": str(child.id), "child_balance": str(outstanding)},
        changed_fields=["balance", "status", "calculation_breakdown"],
        event_data={"child_loan_id": str(child.id), "source_installment_id": str(row.id), "amount": str(outstanding),
                    "signed_agreement": agreement_reference, "credit_approval": approval_reference,
                    "no_cash_movement": True, "net_receivable_change": "0.00"},
    ))
    # Flush and reconcile the persisted ORM balances before committing the
    # transaction. A failed flush/validation is rolled back by the caller.
    db.flush()
    if Decimal(str(parent.balance)) + Decimal(str(child.balance)) != outstanding:
        raise HTTPException(status_code=409, detail="The linked transfer does not conserve total receivables")
    if child.parent_loan_id != parent.id or child.company_id != parent.company_id:
        raise HTTPException(status_code=409, detail="The linked loan relationship is inconsistent")
    reconcile_rollover_accounting(
        transfer=transfer_record, company_id=company_id,
        parent_before=original["balance"], parent_after=parent.balance,
        child_before=Decimal("0"), child_after=child.balance,
    )
    db.commit()
    return {"parent_loan_id": str(parent.id), "child_loan_id": str(child.id),
            "child_loan_reference": child.loan_reference, "child_folio": child.folio_number,
            "transferred_amount": str(outstanding), "parent_balance_after": "0.00",
            "child_balance": str(outstanding), "cash_disbursement": "0.00"}
