from __future__ import annotations

import csv
from collections import defaultdict
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from core.access_control import COMPANY_ROLES, TenantContext, get_tenant_context, require_tenant_roles
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus
from database.models.person import Person
from database.models.user import User
from database.session import get_db


router = APIRouter(prefix="/folio-book", tags=["Loan Folio Book"])


def _scope(query, context: TenantContext):
    query = query.filter(ClientCompanyLoan.company_id == context.company_id)
    if context.branch_id:
        query = query.filter(ClientCompanyLoan.branch_id == context.branch_id)
    return query


def _base_query(db: Session, context: TenantContext):
    return _scope(
        db.query(ClientCompanyLoan).options(
            joinedload(ClientCompanyLoan.borrower).joinedload(Borrower.user).joinedload(User.person),
            joinedload(ClientCompanyLoan.branch),
        ),
        context,
    )


def _borrower_name(loan: ClientCompanyLoan) -> str:
    user = loan.borrower.user if loan.borrower else None
    person = user.person if user else None
    return person.full_name if person else (user.email if user else "Borrower")


def _row(loan: ClientCompanyLoan) -> dict:
    borrower = loan.borrower
    return {
        "loan_id": str(loan.id),
        "folio_number": loan.folio_number,
        "company_code": loan.folio_company_code,
        "group_code": loan.folio_group_code,
        "sequence": loan.folio_sequence,
        "loan_reference": loan.loan_reference,
        "borrower_id": str(loan.borrower_id),
        "borrower_name": _borrower_name(loan),
        "employer_name": borrower.employer_name if borrower else None,
        "branch_id": str(loan.branch_id) if loan.branch_id else None,
        "branch_name": loan.branch.name if loan.branch else None,
        "principal_amount": float(loan.principal_amount or 0),
        "balance": float(loan.balance or 0),
        "status": getattr(loan.status, "value", str(loan.status)),
        "approved_at": loan.approved_at.isoformat() if loan.approved_at else None,
        "disbursed_at": loan.disbursed_at.isoformat() if loan.disbursed_at else None,
        "maturity_date": loan.maturity_date.isoformat() if loan.maturity_date else None,
        "is_overdue": bool(loan.is_overdue),
    }


def _integrity(loans: list[ClientCompanyLoan]) -> dict:
    by_group: dict[str, list[ClientCompanyLoan]] = defaultdict(list)
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


def _parse_status(value: str | None) -> LoanStatus | None:
    if not value:
        return None
    try:
        return LoanStatus(value.strip().lower())
    except ValueError as exc:
        allowed = ", ".join(item.value for item in LoanStatus)
        raise HTTPException(status_code=422, detail=f"Loan status must be one of: {allowed}") from exc


@router.get("")
def folio_book(
    search: str | None = None,
    group_code: str | None = None,
    status: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    query = _base_query(db, context)
    if group_code:
        query = query.filter(ClientCompanyLoan.folio_group_code == group_code.strip().upper())
    parsed_status = _parse_status(status)
    if parsed_status:
        query = query.filter(ClientCompanyLoan.status == parsed_status)
    if search:
        token = f"%{search.strip()}%"
        query = (
            query.join(Borrower, Borrower.id == ClientCompanyLoan.borrower_id)
            .join(User, User.id == Borrower.user_id)
            .outerjoin(Person, Person.user_id == User.id)
            .filter(
                or_(
                    ClientCompanyLoan.folio_number.ilike(token),
                    ClientCompanyLoan.loan_reference.ilike(token),
                    ClientCompanyLoan.folio_group_code.ilike(token),
                    Borrower.employer_name.ilike(token),
                    User.email.ilike(token),
                    User.phone.ilike(token),
                    Person.first_name.ilike(token),
                    Person.middle_name.ilike(token),
                    Person.last_name.ilike(token),
                    Person.national_id.ilike(token),
                    Person.passport_number.ilike(token),
                )
            )
        )
    total = query.count()
    rows = query.order_by(
        ClientCompanyLoan.folio_group_code.asc(),
        ClientCompanyLoan.folio_sequence.asc(),
    ).offset(skip).limit(limit).all()
    all_scoped = _base_query(db, context).all()
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "rows": [_row(item) for item in rows],
        "integrity": _integrity(all_scoped),
    }


@router.get("/lookup/{folio_number}")
def folio_lookup(
    folio_number: str,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    loan = _base_query(db, context).filter(
        ClientCompanyLoan.folio_number == folio_number.strip().upper()
    ).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Folio number was not found in the active company scope")
    return _row(loan)


@router.get("/integrity")
def folio_integrity(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    return _integrity(_base_query(db, context).all())


@router.get("/export.csv")
def export_folio_book(
    group_code: str | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    query = _base_query(db, context)
    if group_code:
        query = query.filter(ClientCompanyLoan.folio_group_code == group_code.strip().upper())
    loans = query.order_by(
        ClientCompanyLoan.folio_group_code.asc(),
        ClientCompanyLoan.folio_sequence.asc(),
    ).all()
    stream = StringIO()
    writer = csv.DictWriter(stream, fieldnames=[
        "folio_number", "group_code", "sequence", "loan_reference", "borrower_name",
        "employer_name", "branch_name", "principal_amount", "balance", "status",
        "approved_at", "disbursed_at", "maturity_date", "is_overdue",
    ])
    writer.writeheader()
    for loan in loans:
        payload = _row(loan)
        writer.writerow({key: payload.get(key) for key in writer.fieldnames})
    return Response(
        content=stream.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=loanhub-folio-book.csv"},
    )
