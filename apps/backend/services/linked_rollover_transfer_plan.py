"""Pre-posting checks for carrying a final installment into a linked facility.

This module deliberately generates a balanced transfer plan, not a payment or
credit disbursement. Posting requires a dedicated atomic ledger transaction.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException

from services.final_installment_rollover_preview import preview_final_installment_rollover

CENT = Decimal("0.01")


def amount(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def prepare_linked_rollover(
    loan, installment_id, *, approved_amount: Decimal,
    effective_due_date: date, agreement_reference: str,
    approval_reference: str, as_of: date,
) -> dict:
    proposal = preview_final_installment_rollover(loan, installment_id)
    original_balance = amount(proposal["current_loan_balance"])
    confirmed = amount(approved_amount)
    if confirmed != original_balance:
        raise HTTPException(status_code=409, detail="Approved transfer amount does not equal the outstanding parent balance")
    if effective_due_date <= as_of:
        raise HTTPException(status_code=422, detail="The signed rollover must specify a future repayment date")
    if len((agreement_reference or "").strip()) < 5:
        raise HTTPException(status_code=422, detail="A signed amendment reference is required")
    if len((approval_reference or "").strip()) < 5:
        raise HTTPException(status_code=422, detail="A credit approval reference is required")
    if getattr(loan, "is_top_up", False):
        raise HTTPException(status_code=409, detail="Top-up-linked facilities require separate settlement reconciliation")
    if getattr(loan, "renewal_cycle_count", 0):
        raise HTTPException(status_code=409, detail="Maturity-renewed facilities require separate cycle reconciliation")
    if any(getattr(row, "is_superseded", False) for row in loan.installments):
        raise HTTPException(status_code=409, detail="Superseded schedules require manual reconciliation")

    transfer = {
        **proposal,
        "approved_transfer_amount": str(confirmed),
        "agreed_due_date": effective_due_date.isoformat(),
        "agreement_reference": agreement_reference.strip(),
        "approval_reference": approval_reference.strip(),
        "parent_balance_after_transfer": "0.00",
        "child_opening_receivable": str(confirmed),
        "total_receivable_before": str(original_balance),
        "total_receivable_after": str(confirmed),
        "new_cash_disbursement": "0.00",
        "new_interest_or_fee": "0.00",
        "transfer_balances": True,
        "posting_enabled": False,
        "posting_blocker": "Requires atomic parent-child subledger posting, immutable transfer record, and dedicated reversal workflow",
    }
    from services.rollover_receivable_reconciliation import validate_rollover_receivable_transfer
    transfer["receivable_reconciliation"] = validate_rollover_receivable_transfer(
        plan=transfer, parent_outstanding=original_balance,
    )
    return transfer
