from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_ROLES,
    PLATFORM_ROLES,
    TenantContext,
    get_current_active_user,
    get_user_context,
)
from database.models.enums import UserRole
from database.models.user import User
from database.schemas.analytics import AnalyticsDashboardRead
from database.session import get_db
from services.analytics_service import (
    build_borrower_analytics,
    build_company_analytics,
    build_platform_analytics,
)


router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _range(
    date_from: date | None,
    date_to: date | None,
) -> tuple[date, date]:
    end = date_to or date.today()
    start = date_from or (end - timedelta(days=364))
    if start > end:
        raise HTTPException(status_code=400, detail="date_from cannot be later than date_to")
    if (end - start).days > 1095:
        raise HTTPException(status_code=400, detail="Analytics range cannot exceed three years")
    return start, end


@router.get("/company", response_model=AnalyticsDashboardRead)
def company_analytics(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    granularity: str | None = Query(default=None, pattern="^(day|week|month)$"),
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    if context.role not in COMPANY_ROLES or not context.company_id:
        raise HTTPException(status_code=403, detail="Company analytics require an active company role")
    start, end = _range(date_from, date_to)
    try:
        return build_company_analytics(
            db,
            context=context,
            date_from=start,
            date_to=end,
            granularity=granularity,
            branch_id=branch_id,
        )
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error


@router.get("/platform", response_model=AnalyticsDashboardRead)
def platform_analytics(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    granularity: str | None = Query(default=None, pattern="^(day|week|month)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role not in PLATFORM_ROLES:
        raise HTTPException(status_code=403, detail="Platform analytics require a platform role")
    start, end = _range(date_from, date_to)
    return build_platform_analytics(
        db,
        current_user=current_user,
        date_from=start,
        date_to=end,
        granularity=granularity,
    )


@router.get("/borrower", response_model=AnalyticsDashboardRead)
def borrower_analytics(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    granularity: str | None = Query(default=None, pattern="^(day|week|month)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.BORROWER:
        raise HTTPException(status_code=403, detail="Borrower analytics require a borrower account")
    start, end = _range(date_from, date_to)
    try:
        return build_borrower_analytics(
            db,
            current_user=current_user,
            date_from=start,
            date_to=end,
            granularity=granularity,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
