"""Read-only validation of transaction-specific reversal authorization.

The checker identity is verified against current company membership separately.
This routine never records approval or performs financial mutations.
"""
from fastapi import HTTPException
from database.models.loan_rollover_reversal_approval import LoanRolloverReversalApproval
from database.models.loan_rollover_reversal_request import LoanRolloverReversalRequest
from services.rollover_checker_identity import verify_rollover_checker_identity


def require_rollover_reversal_approval(
    db, *, company_id, transfer_id, maker_user_id, checker_user_id,
    approval_reference,
):
    decision = db.query(LoanRolloverReversalApproval).filter(
        LoanRolloverReversalApproval.company_id == company_id,
        LoanRolloverReversalApproval.transfer_id == transfer_id,
        LoanRolloverReversalApproval.approval_reference == approval_reference,
        LoanRolloverReversalApproval.decision == "approved",
        LoanRolloverReversalApproval.maker_user_id == maker_user_id,
        LoanRolloverReversalApproval.checker_user_id == checker_user_id,
    ).one_or_none()
    if decision is None:
        raise HTTPException(status_code=409, detail="Approved independent reversal decision not found")
    request = db.query(LoanRolloverReversalRequest).filter(
        LoanRolloverReversalRequest.company_id == company_id,
        LoanRolloverReversalRequest.transfer_id == transfer_id,
        LoanRolloverReversalRequest.maker_user_id == maker_user_id,
    ).one_or_none()
    evidence = decision.evidence if isinstance(decision.evidence, dict) else {}
    if request is None or evidence.get("maker_request_id") != str(request.id):
        raise HTTPException(
            status_code=409,
            detail="Approved reversal decision is not linked to the authenticated maker request",
        )
    verify_rollover_checker_identity(
        db, company_id=company_id,
        maker_user_id=maker_user_id, checker_user_id=checker_user_id,
    )
    return decision
