from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import event

from database.models.credit_committee import CreditCommitteeCondition


_installed = False


def _normalize_condition_date(mapper, connection, target: CreditCommitteeCondition) -> None:  # noqa: ARG001
    if isinstance(target.due_date, str):
        try:
            target.due_date = date.fromisoformat(target.due_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Credit-condition due date must use YYYY-MM-DD format") from exc


def install_credit_committee_integrity() -> None:
    """Install Credit Committee data-integrity listeners.

    Credit Committee review is an optional governance workflow. Its decisions,
    votes and conditions remain recorded and visible, but they do not impose a
    universal ORM transaction gate on application approval, loan creation or
    loan activation. Authorised lending roles may proceed using the available
    underwriting evidence when committee review is not required by their own
    operating process.
    """
    global _installed
    if _installed:
        return
    event.listen(CreditCommitteeCondition, "before_insert", _normalize_condition_date)
    event.listen(CreditCommitteeCondition, "before_update", _normalize_condition_date)
    _installed = True
