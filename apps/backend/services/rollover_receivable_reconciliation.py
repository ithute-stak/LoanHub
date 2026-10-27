"""Financial reconciliation requirements for an approved parent-to-child rollover.

The general ledger may represent loans in a shared receivable control account.
Moving a balance between two borrower-loan subledgers is therefore not a
cash collection or a new advance, and must not inflate GL balances.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException

CENT = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def validate_rollover_receivable_transfer(*, plan: dict, parent_outstanding, child_existing_outstanding=0) -> dict:
    """Prove the intended transfer is debt-neutral, before an atomic DB posting.

    Returned entries describe the required loan subledger transfer, not posted
    journal lines. No fabricated debit/credit is sent to GL control accounts.
    """
    moved = money(plan["approved_transfer_amount"])
    parent = money(parent_outstanding)
    child = money(child_existing_outstanding)
    if moved <= 0 or parent != moved:
        raise HTTPException(status_code=409, detail="Parent receivable must equal the approved positive rollover amount")
    if child != 0:
        raise HTTPException(status_code=409, detail="Child facility already has a receivable")
    if money(plan["new_cash_disbursement"]) != 0 or money(plan["new_interest_or_fee"]) != 0:
        raise HTTPException(status_code=409, detail="Rollover cannot create a new disbursement, interest or fee")
    if money(plan["parent_balance_after_transfer"]) != 0:
        raise HTTPException(status_code=409, detail="Parent receivable must be fully discharged through the transfer")
    if money(plan["child_opening_receivable"]) != moved:
        raise HTTPException(status_code=409, detail="Child opening receivable must match the transferred amount")
    if money(plan["total_receivable_before"]) != money(plan["total_receivable_after"]):
        raise HTTPException(status_code=409, detail="Combined receivables must remain unchanged")
    return {
        "parent_reduction": str(moved),
        "child_increase": str(moved),
        "net_receivable_change": "0.00",
        "net_cash_change": "0.00",
        "general_ledger_control_change": "0.00",
        "subledger_postings": [
            {"loan_id": plan["parent_loan_id"], "direction": "transfer_out", "amount": str(moved)},
            {"loan_id": None, "direction": "transfer_in", "amount": str(moved)},
        ],
        "requires_immutable_transfer_id": True,
        "requires_atomic_posting": True,
    }
