"""Authenticate maker-initiated review requests without financial posting."""
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from database.models.loan_rollover_transfer import LoanRolloverTransfer
from database.models.loan_rollover_reversal_request import LoanRolloverReversalRequest
from database.models.loan_rollover_reversal_approval import LoanRolloverReversalApproval


def record_rollover_reversal_request(db, *, company_id, transfer_id, maker_user_id, request_reference, reason):
    if not request_reference.strip() or len(reason.strip()) < 12:
        raise HTTPException(status_code=422, detail="A reference and detailed reason are required")
    transfer = db.query(LoanRolloverTransfer).filter(
        LoanRolloverTransfer.id == transfer_id,
        LoanRolloverTransfer.company_id == company_id,
    ).with_for_update().one_or_none()
    if transfer is None:
        raise HTTPException(status_code=404, detail="Rollover transfer not found")
    if transfer.status != "posted":
        raise HTTPException(status_code=409, detail="Only posted transfers may be reviewed")
    if db.query(LoanRolloverReversalApproval.id).filter(
        LoanRolloverReversalApproval.transfer_id == transfer.id
    ).first():
        raise HTTPException(status_code=409, detail="Checker decision already exists")
    if db.query(LoanRolloverReversalRequest.id).filter(
        LoanRolloverReversalRequest.transfer_id == transfer.id
    ).first():
        raise HTTPException(status_code=409, detail="Maker request already exists")
    record = LoanRolloverReversalRequest(
        company_id=company_id, transfer_id=transfer.id,
        maker_user_id=maker_user_id, request_reference=request_reference.strip(),
        reason=reason.strip(),
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Maker request already recorded")
    db.refresh(record)
    return {"request_id": str(record.id), "transfer_id": str(transfer.id),
            "status": "pending_checker_review", "posting_enabled": False}
