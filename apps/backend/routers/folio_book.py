from __future__ import annotations

from collections import defaultdict
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
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import UserRole
from database.session import get_db
from services.folio_book_service import FolioBookFilters, _company_loans_query, _row_payload, build_folio_book, folio_book_csv


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




def _base_query(db: Session, context: TenantContext):
    """Compatibility query used by borrower folio-history routes."""
    query = _company_loans_query(db, context)
    if context.branch_id:
        query = query.filter(ClientCompanyLoan.branch_id == context.branch_id)
    return query


def _row(loan: ClientCompanyLoan) -> dict:
    """Compatibility row serializer backed by the canonical folio service."""
    return _row_payload(loan)

def _integrity(loans: list) -> dict:
    """Compatibility integrity summary for legacy callers and tests."""
    by_group: dict[str, list] = defaultdict(list)
    missing: list[str] = []
    malformed: list[str] = []
    seen_numbers: dict[str, list[str]] = defaultdict(list)

    for loan in loans:
        if not loan.folio_number or not loan.folio_group_code or not loan.folio_sequence:
            missing.append(str(loan.id))
            continue
        expected = f"{loan.folio_company_code}-{loan.folio_group_code}-{int(loan.folio_sequence):05d}"
        if loan.folio_number != expected:
            malformed.append(loan.folio_number)
        seen_numbers[loan.folio_number].append(str(loan.id))
        by_group[loan.folio_group_code].append(loan)

    duplicate_numbers = {number: ids for number, ids in seen_numbers.items() if len(ids) > 1}
    groups = []
    total_gaps = 0
    for group_code, rows in sorted(by_group.items()):
        sequences = sorted({int(row.folio_sequence) for row in rows if row.folio_sequence})
        maximum = sequences[-1] if sequences else 0
        existing = set(sequences)
        gaps = [value for value in range(1, maximum + 1) if value not in existing]
        total_gaps += len(gaps)
        company_code = rows[0].folio_company_code if rows else ""
        groups.append({
            "company_code": company_code,
            "group_code": group_code,
            "loan_count": len(rows),
            "first_sequence": sequences[0] if sequences else None,
            "last_sequence": maximum or None,
            "next_sequence": maximum + 1,
            "next_folio": f"{company_code}-{group_code}-{maximum + 1:05d}",
            "gap_count": len(gaps),
            "gaps": gaps[:100],
        })

    return {
        "healthy": not missing and not malformed and not duplicate_numbers and total_gaps == 0,
        "loan_count": len(loans),
        "missing_folio_count": len(missing),
        "missing_loan_ids": missing[:100],
        "malformed_folio_count": len(malformed),
        "malformed_folios": malformed[:100],
        "duplicate_folio_count": len(duplicate_numbers),
        "duplicate_folios": duplicate_numbers,
        "gap_count": total_gaps,
        "groups": groups,
    }

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


@router.get("/integrity")
def folio_integrity(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, FOLIO_BOOK_ROLES)
    payload = build_folio_book(
        db,
        context=context,
        filters=FolioBookFilters(),
        skip=0,
        limit=100_000,
    )
    summary = payload["summary"]
    groups = [
        {
            "company_code": item["company_code"],
            "group_code": item["group_code"],
            "loan_count": item["loan_count"],
            "first_sequence": item["first_sequence"],
            "last_sequence": item["last_sequence"],
            "next_sequence": item["next_sequence"],
            "next_folio": item["next_folio_number"],
            "gap_count": item["gap_count"],
            "gaps": item["gaps"],
        }
        for item in payload["sequence_books"]
    ]
    return {
        "healthy": bool(summary["integrity_ok"] and summary["gap_count"] == 0),
        "loan_count": summary["total_loans"],
        "missing_folio_count": summary["missing_folio_count"],
        "malformed_folio_count": summary["invalid_format_count"] + summary["component_mismatch_count"],
        "duplicate_folio_count": summary["duplicate_folio_count"],
        "gap_count": summary["gap_count"],
        "groups": groups,
    }


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
