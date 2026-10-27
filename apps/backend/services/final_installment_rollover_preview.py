"""Preview a last-installment arrears rollover before any credit agreement is signed."""
from __future__ import annotations
from decimal import Decimal
from fastapi import HTTPException
from database.models.enums import InstallmentStatus, LoanStatus


def preview_final_installment_rollover(loan, installment_id):
    if loan.status not in {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}:
        raise HTTPException(status_code=409, detail="Only active loans may be considered for rollover")
    schedule = sorted(
        (row for row in loan.installments if not row.is_superseded),
        key=lambda row: row.installment_number,
    )
    row = next((item for item in schedule if item.id == installment_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Installment not found")
    if row != schedule[-1]:
        raise HTTPException(status_code=409, detail="This is not the final active installment")
    if row.status in {InstallmentStatus.WAIVED, InstallmentStatus.PAID}:
        raise HTTPException(status_code=409, detail="Paid or waived installments are ineligible")
    paid = Decimal(str(row.paid_amount or 0))
    remainder = Decimal(str(row.total_due or 0)) - paid
    if paid <= 0 or remainder <= 0:
        raise HTTPException(status_code=409, detail="A partially paid final installment is required")
    balance = Decimal(str(loan.balance or 0))
    if balance != remainder:
        raise HTTPException(status_code=409, detail="Loan balance must exactly match the remaining final installment before linked rollover")
    return {
        "parent_loan_id": str(loan.id),
        "borrower_id": str(loan.borrower_id),
        "company_id": str(loan.company_id),
        "branch_id": str(loan.branch_id) if loan.branch_id else None,
        "source_installment_id": str(row.id),
        "unpaid_remainder": str(remainder),
        "current_loan_balance": str(balance),
        "proposed_child_principal": str(remainder),
        "proposed_cash_disbursement": "0.00",
        "inherited_repayment_type": loan.repayment_type.value,
        "inherited_interest_rate": str(loan.interest_rate),
        "inherited_calculation_method": loan.calculation_method,
        "inherited_cdas_collection_enabled": bool(loan.cdas_collection_enabled),
        "requires_signed_amendment": True,
        "requires_credit_approval": True,
        "ready_to_post": False,
        "note": "Preview only. No child loan, cash transaction, capitalization, or revised interest has been posted.",
    }
