from __future__ import annotations

from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.access_control import (
    COLLECTIONS_ROLES,
    COMPANY_MANAGEMENT_ROLES,
    FINANCE_ROLES,
    LENDING_ROLES,
    TenantContext,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.enums import UserRole
from database.session import get_db
from services.folio_book_service import FolioBookFilters, build_folio_book, folio_book_csv


router = APIRouter(prefix="/folio-book", tags=["Loan Folio Book"])

FOLIO_BOOK_ROLES = (
    COMPANY_MANAGEMENT_ROLES
    | LENDING_ROLES
    | FINANCE_ROLES
    | COLLECTIONS_ROLES
    | {
        UserRole.AUDITOR,
        UserRole.RISK_MANAGER,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.REGULATORY_REPORTING_OFFICER,
    }
)


def _filters(
    search: str | None,
    group_code: str | None,
    status: str | None,
    branch_id: UUID | None,
) -> FolioBookFilters:
    return FolioBookFilters(
        search=search,
        group_code=group_code,
        status=status,
        branch_id=branch_id,
    )


@router.get("")
def get_folio_book(
    search: str | None = Query(default=None, max_length=200),
    group_code: str | None = Query(default=None, max_length=20),
    status: str | None = Query(default=None, max_length=40),
    branch_id: UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, FOLIO_BOOK_ROLES)
    return build_folio_book(
        db,
        context=context,
        filters=_filters(search, group_code, status, branch_id),
        skip=skip,
        limit=limit,
    )


@router.get("/export.csv")
def export_folio_book_csv(
    search: str | None = Query(default=None, max_length=200),
    group_code: str | None = Query(default=None, max_length=20),
    status: str | None = Query(default=None, max_length=40),
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, FOLIO_BOOK_ROLES)
    payload = build_folio_book(
        db,
        context=context,
        filters=_filters(search, group_code, status, branch_id),
        skip=0,
        limit=100_000,
    )
    content = folio_book_csv(payload)
    return StreamingResponse(
        BytesIO(content),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=LoanHub-Folio-Book.csv",
            "Cache-Control": "private, no-store, max-age=0",
        },
    )
