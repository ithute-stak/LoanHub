"""Pure financial calculations for reversing a linked receivable transfer.

No database mutations occur here. Original contractual principal, interest,
fees and previously collected payments must remain historically intact.
"""
from decimal import Decimal
from fastapi import HTTPException


def prepare_rollover_compensation_balances(*, transfer_amount, parent_balance, child_balance,
                                           child_amount_paid, original_parent_balance):
    amount = Decimal(str(transfer_amount))
    parent = Decimal(str(parent_balance))
    child = Decimal(str(child_balance))
    child_paid = Decimal(str(child_amount_paid))
    original = Decimal(str(original_parent_balance))
    if amount <= 0 or parent != 0 or child != amount or child_paid != 0:
        raise HTTPException(status_code=409, detail="Rollover balances changed; compensation requires manual reconciliation")
    if original != amount:
        raise HTTPException(status_code=409, detail="Historical parent balance differs from transfer")
    return {
        "parent_balance_after": amount,
        "child_balance_after": Decimal("0"),
        "net_receivable_change": (amount + Decimal("0")) - (parent + child),
        "amount": amount,
        "no_cash_movement": True,
    }
