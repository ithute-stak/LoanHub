from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from database.models.client_loan_company import ClientCompanyLoan
from database.models.credit_committee import CreditCommitteeCase, CreditCommitteeCondition
from database.models.enums import LoanStatus
from database.models.professional_lending import DirectLoanApplication


_APPROVED_DECISIONS = {"approved", "conditionally_approved"}
_RESOLVED_CONDITIONS = {"satisfied", "waived"}
_installed = False


def _pending_case(session: Session, application_id) -> CreditCommitteeCase | None:
    candidates = list(session.new) + list(session.dirty) + list(session.identity_map.values())
    for candidate in candidates:
        if isinstance(candidate, CreditCommitteeCase) and candidate.application_id == application_id:
            return candidate
    return None


def _committee_case(session: Session, application: DirectLoanApplication) -> CreditCommitteeCase | None:
    pending = _pending_case(session, application.id)
    if pending is not None:
        return pending
    with session.no_autoflush:
        return (
            session.query(CreditCommitteeCase)
            .filter(
                CreditCommitteeCase.company_id == application.company_id,
                CreditCommitteeCase.application_id == application.id,
            )
            .first()
        )


def _open_condition_count(session: Session, case_id, condition_types: set[str]) -> int:
    pending_rows = [
        row
        for row in list(session.new) + list(session.dirty) + list(session.identity_map.values())
        if isinstance(row, CreditCommitteeCondition)
        and row.case_id == case_id
        and row.condition_type in condition_types
        and row.status not in _RESOLVED_CONDITIONS
        and row not in session.deleted
    ]
    pending_ids = {row.id for row in pending_rows if row.id is not None}
    with session.no_autoflush:
        persisted = (
            session.query(CreditCommitteeCondition)
            .filter(
                CreditCommitteeCondition.case_id == case_id,
                CreditCommitteeCondition.condition_type.in_(list(condition_types)),
                CreditCommitteeCondition.status.notin_(list(_RESOLVED_CONDITIONS)),
            )
            .all()
        )
    persisted = [row for row in persisted if row.id not in pending_ids and row not in session.deleted]
    return len(pending_rows) + len(persisted)


def _require_case_for_target_status(session: Session, application: DirectLoanApplication, target_status: str) -> None:
    if not bool(getattr(application, "credit_committee_required", False)):
        return
    case = _committee_case(session, application)
    if target_status == "approved":
        if not case or case.final_decision not in _APPROVED_DECISIONS:
            raise HTTPException(
                status_code=409,
                detail="Credit Committee approval is required before this application can be approved",
            )
        blocking = _open_condition_count(session, case.id, {"pre_contract"})
        if blocking:
            raise HTTPException(
                status_code=409,
                detail=f"{blocking} pre-contract Credit Committee condition(s) must be satisfied or formally waived before loan approval",
            )
    elif target_status == "rejected":
        if not case or case.final_decision != "rejected":
            raise HTTPException(
                status_code=409,
                detail="A final Credit Committee rejection is required before this governed application can be rejected",
            )


def _require_loan_creation_clearance(session: Session, loan: ClientCompanyLoan) -> None:
    if not loan.direct_application_id:
        return
    application = session.get(DirectLoanApplication, loan.direct_application_id)
    if not application or not bool(getattr(application, "credit_committee_required", False)):
        return
    _require_case_for_target_status(session, application, "approved")


def _require_disbursement_clearance(session: Session, loan: ClientCompanyLoan) -> None:
    if not loan.direct_application_id:
        return
    application = session.get(DirectLoanApplication, loan.direct_application_id)
    if not application or not bool(getattr(application, "credit_committee_required", False)):
        return
    case = _committee_case(session, application)
    if not case or case.final_decision not in _APPROVED_DECISIONS:
        raise HTTPException(status_code=409, detail="Credit Committee clearance is missing for this loan")
    blocking = _open_condition_count(session, case.id, {"pre_contract", "pre_disbursement"})
    if blocking:
        raise HTTPException(
            status_code=409,
            detail=f"{blocking} Credit Committee pre-disbursement condition(s) remain unresolved",
        )


def _normalize_condition_date(mapper, connection, target: CreditCommitteeCondition) -> None:  # noqa: ARG001
    if isinstance(target.due_date, str):
        try:
            target.due_date = date.fromisoformat(target.due_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Credit-condition due date must use YYYY-MM-DD format") from exc


def _before_flush(session: Session, flush_context, instances) -> None:  # noqa: ARG001
    # Enforce the governance boundary at the ORM transaction layer so no
    # alternate router/service can bypass committee approval or conditions.
    for obj in list(session.new):
        if isinstance(obj, ClientCompanyLoan):
            _require_loan_creation_clearance(session, obj)

    for obj in list(session.dirty):
        if isinstance(obj, DirectLoanApplication):
            history = inspect(obj).attrs.status.history
            if history.has_changes() and history.added:
                target = str(history.added[-1] or "").lower()
                if target in {"approved", "rejected"}:
                    _require_case_for_target_status(session, obj, target)
        elif isinstance(obj, ClientCompanyLoan):
            history = inspect(obj).attrs.status.history
            if history.has_changes() and history.added:
                target = history.added[-1]
                target_value = getattr(target, "value", str(target)).lower()
                if target_value == LoanStatus.ACTIVE.value:
                    _require_disbursement_clearance(session, obj)


def install_credit_committee_integrity() -> None:
    global _installed
    if _installed:
        return
    event.listen(Session, "before_flush", _before_flush)
    event.listen(CreditCommitteeCondition, "before_insert", _normalize_condition_date)
    event.listen(CreditCommitteeCondition, "before_update", _normalize_condition_date)
    _installed = True
