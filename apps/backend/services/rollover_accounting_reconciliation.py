"""Read-only accounting policy for internal, noncash rollover transfers.

LoanHub's chart of accounts is company-scoped. An intra-company transfer
changes the loan subledger only; it must NOT invent cash, income, or a journal
debit/credit to the same company receivable account. A future journal policy
requires separate accounting approval before posting can be enabled.
"""
from decimal import Decimal, InvalidOperation
from fastapi import HTTPException

_COMPONENT_ACCOUNTS = {
    "principal": "1100",
    "interest": "1110",
    "fees": "1120",
}


def reconcile_rollover_accounting(*, transfer, parent_before, parent_after,
                                  child_before, child_after, company_id):
    if transfer.company_id != company_id:
        raise HTTPException(status_code=404, detail="Rollover transfer not found")
    def money(value):
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise HTTPException(status_code=409, detail="Invalid rollover monetary value") from exc
        if not amount.is_finite():
            raise HTTPException(status_code=409, detail="Non-finite rollover monetary value")
        return amount

    amounts = {
        "principal": money(transfer.principal_component),
        "interest": money(transfer.interest_component),
        "fees": money(transfer.fee_component),
    }
    total = money(transfer.transfer_amount)
    if any(amount < 0 for amount in amounts.values()) or total <= 0:
        raise HTTPException(status_code=409, detail="Invalid rollover component amounts")
    if sum(amounts.values()) != total:
        raise HTTPException(status_code=409, detail="Rollover accounting components do not balance")
    parent_start, parent_end = money(parent_before), money(parent_after)
    child_start, child_end = money(child_before), money(child_after)
    if any(value < 0 for value in (parent_start, parent_end, child_start, child_end)):
        raise HTTPException(status_code=409, detail="Negative rollover receivable balance")
    if parent_start + child_start != parent_end + child_end:
        raise HTTPException(status_code=409, detail="Rollover changes company receivables")
    if parent_start - parent_end != total:
        raise HTTPException(status_code=409, detail="Parent receivable movement does not match transfer")
    if child_end - child_start != total:
        raise HTTPException(status_code=409, detail="Child receivable movement does not match transfer")
    return {
        "balanced": True,
        "no_cash_movement": True,
        "no_new_income": True,
        "company_gl_net_change": "0.00",
        "component_accounts": {key: code for key, code in _COMPONENT_ACCOUNTS.items()
                               if amounts[key] > 0},
        "transferred_components": {key: str(amounts[key]) for key in amounts},
        "transfer_amount": str(total),
        "journal_policy": "intra_company_subledger_reclassification",
        "posting_enabled": False,
    }
