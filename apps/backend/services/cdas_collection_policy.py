from __future__ import annotations

from datetime import date, datetime
from typing import Iterable
from uuid import UUID


AUTHORIZATION_BASIS = "LOAN_LEVEL_CDAS_COLLECTION_SELECTION"
COLLECTION_METHOD = "cdas_payroll"
COLLECTION_MODE = "automatic_monthly_payroll"


def build_cdas_collection_plan(
    *,
    enabled: bool,
    installment_due_dates: Iterable[date | str],
    term_count: int,
    selected_by_user_id: UUID | None,
    selected_at: datetime | None = None,
) -> dict:
    """Build the server-owned plan persisted on an application or loan.

    Clients select only whether the loan is collected through CDAS. Provider
    fields such as ItemCode, LoanPolicy and DeductionID remain server/provider
    controlled and are deliberately excluded from this plan.
    """
    if not enabled:
        return {}

    normalized_dates = [
        value.isoformat() if isinstance(value, date) else str(value)
        for value in installment_due_dates
    ]
    plan = {
        "method": COLLECTION_METHOD,
        "mode": COLLECTION_MODE,
        "authorization_basis": AUTHORIZATION_BASIS,
        "term_count": int(term_count),
        "installment_due_dates": normalized_dates,
        "first_payment_date": normalized_dates[0] if normalized_dates else None,
        "selected_by_user_id": str(selected_by_user_id) if selected_by_user_id else None,
    }
    if selected_at is not None:
        plan["selected_at"] = selected_at.isoformat()
    return plan
