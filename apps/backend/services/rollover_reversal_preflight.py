"""Read-only prerequisites for a compensating rollover reversal.

This module MUST NOT restore balances or rewrite an append-only transfer row.
An actual reversal needs its own durable compensating journal and approval.
"""
from decimal import Decimal
from fastapi import HTTPException


def validate_rollover_reversal_preflight(*, transfer, parent, child, child_installments, child_payments_count: int, actor_company_id):
    if transfer.company_id != actor_company_id or parent.company_id != actor_company_id or child.company_id != actor_company_id:
        raise HTTPException(status_code=404, detail="Rollover not found")
    if transfer.parent_loan_id != parent.id or transfer.child_loan_id != child.id or child.parent_loan_id != parent.id:
        raise HTTPException(status_code=409, detail="Rollover loan linkage does not reconcile")
    if transfer.status != "posted":
        raise HTTPException(status_code=409, detail="Only posted rollovers are eligible for reversal review")
    if child_payments_count != 0 or Decimal(str(child.amount_paid)) != 0:
        raise HTTPException(status_code=409, detail="Child loan has payment activity; specialist settlement required")
    if Decimal(str(child.balance)) != Decimal(str(transfer.transfer_amount)):
        raise HTTPException(status_code=409, detail="Child balance has changed since transfer")
    if Decimal(str(parent.balance)) != 0:
        raise HTTPException(status_code=409, detail="Parent already has an outstanding balance")
    if getattr(child, "status", None) is None or str(getattr(child.status, "value", child.status)) != "active":
        raise HTTPException(status_code=409, detail="Child facility is no longer active")
    if len(child_installments) != 1:
        raise HTTPException(status_code=409, detail="Child schedule was modified")
    installment = child_installments[0]
    if installment.is_superseded or Decimal(str(installment.paid_amount)) != 0 or Decimal(str(installment.total_due)) != Decimal(str(transfer.transfer_amount)):
        raise HTTPException(status_code=409, detail="Child installment does not match transfer")
    # A schedule can retain the same total while quietly moving debt between
    # principal, earned interest and fees. That is not a valid compensation.
    for schedule_field, ledger_field in (
        ("principal_due", "principal_component"),
        ("interest_due", "interest_component"),
        ("fee_due", "fee_component"),
    ):
        if Decimal(str(getattr(installment, schedule_field))) != Decimal(str(getattr(transfer, ledger_field))):
            raise HTTPException(
                status_code=409,
                detail="Child installment component classification changed since rollover",
            )
    original = (parent.calculation_breakdown or {}).get("linked_rollover_out") or {}
    if str(original.get("child_loan_id")) != str(child.id):
        raise HTTPException(status_code=409, detail="Original transfer evidence is missing")
    if Decimal(str(original.get("amount", "-1"))) != Decimal(str(transfer.transfer_amount)):
        raise HTTPException(status_code=409, detail="Original transfer amount does not reconcile")
    return {
        "eligible_for_manual_review": True,
        "posting_enabled": False,
        "transfer_id": str(transfer.id),
        "amount": str(transfer.transfer_amount),
        "requires_compensating_journal": True,
        "requires_independent_approval": True,
    }
