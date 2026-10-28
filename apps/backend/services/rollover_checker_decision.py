"""Record a checker decision using an authenticated tenant identity.

The original transfer actor is the maker-of-record. No user-controlled checker
or maker IDs are trusted. This does not execute or enable loan reversal.
"""
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from database.models.loan_rollover_transfer import LoanRolloverTransfer
from database.models.loan_rollover_reversal_approval import LoanRolloverReversalApproval
from database.models.loan_rollover_reversal_request import LoanRolloverReversalRequest
from services.rollover_checker_identity import verify_rollover_checker_identity


def record_rollover_checker_decision(
    db, *, company_id, transfer_id, checker_user_id, approval_reference,
    decision, reason,
):
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=422, detail="Invalid reversal decision")
    transfer = db.query(LoanRolloverTransfer).filter(
        LoanRolloverTransfer.id == transfer_id,
        LoanRolloverTransfer.company_id == company_id,
    ).with_for_update().one_or_none()
    if transfer is None:
        raise HTTPException(status_code=404, detail="Rollover transfer not found")
    if transfer.status != "posted":
        raise HTTPException(status_code=409, detail="Only posted transfers can be reviewed")
    request = db.query(LoanRolloverReversalRequest).filter(
        LoanRolloverReversalRequest.transfer_id == transfer.id,
        LoanRolloverReversalRequest.company_id == company_id,
    ).one_or_none()
    if request is None:
        raise HTTPException(status_code=409, detail="Authenticated maker reversal request required")
    maker_id = request.maker_user_id
    verify_rollover_checker_identity(
        db, company_id=company_id, maker_user_id=maker_id,
        checker_user_id=checker_user_id,
    )
    existing = db.query(LoanRolloverReversalApproval.id).filter(
        LoanRolloverReversalApproval.transfer_id == transfer.id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Decision already recorded for this transfer")
    record = LoanRolloverReversalApproval(
        company_id=company_id, transfer_id=transfer.id,
        maker_user_id=maker_id, checker_user_id=checker_user_id,
        approval_reference=approval_reference, decision=decision, reason=reason,
        evidence={"checker_authenticated": True, "maker_source": "authenticated_reversal_request",
                  "maker_request_id": str(request.id),
                  "financial_posting_enabled": False},
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Approval reference or transfer already recorded")
    db.refresh(record)
    return {"decision_id": str(record.id), "transfer_id": str(transfer.id),
            "decision": record.decision, "posting_enabled": False}
