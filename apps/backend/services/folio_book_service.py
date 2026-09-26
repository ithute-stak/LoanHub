from __future__ import annotations

import csv
import io
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from core.access_control import COMPANY_MANAGEMENT_ROLES, TenantContext
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.user import User


_FOLIO_PATTERN = re.compile(r"^[A-Z0-9]{2,8}-[A-Z0-9]{2,8}-\d{5,}$")
_MAX_REPORTED_GAPS_PER_BOOK = 100


@dataclass(frozen=True)
class FolioBookFilters:
    search: str | None = None
    group_code: str | None = None
    status: str | None = None
    branch_id: UUID | None = None


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _expected_folio(loan: ClientCompanyLoan) -> str | None:
    if not loan.folio_company_code or not loan.folio_group_code or not loan.folio_sequence:
        return None
    return f"{loan.folio_company_code}-{loan.folio_group_code}-{int(loan.folio_sequence):05d}"


def _loan_rows_query(db: Session, context: TenantContext):
    query = (
        db.query(ClientCompanyLoan)
        .options(
            joinedload(ClientCompanyLoan.company),
            joinedload(ClientCompanyLoan.branch),
            joinedload(ClientCompanyLoan.borrower)
            .joinedload(Borrower.user)
            .joinedload(User.person),
            joinedload(ClientCompanyLoan.borrower).joinedload(Borrower.employer_group),
        )
        .filter(ClientCompanyLoan.company_id == context.company_id)
    )
    if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:
        query = query.filter(ClientCompanyLoan.branch_id == context.branch_id)
    return query


def _borrower_values(loan: ClientCompanyLoan) -> tuple[str, str | None]:
    borrower = loan.borrower
    person = borrower.user.person if borrower and borrower.user else None
    name = person.full_name if person else "Borrower"
    identity = None
    if person:
        identity = person.national_id or person.passport_number
    return name, identity


def _row_payload(loan: ClientCompanyLoan) -> dict[str, Any]:
    borrower_name, borrower_identity = _borrower_values(loan)
    group = loan.borrower.employer_group if loan.borrower else None
    branch = loan.branch
    expected = _expected_folio(loan)
    actual = str(loan.folio_number or "").strip()
    integrity_issues: list[str] = []
    if not actual:
        integrity_issues.append("missing_folio")
    elif not _FOLIO_PATTERN.fullmatch(actual):
        integrity_issues.append("invalid_format")
    if expected and actual and actual != expected:
        integrity_issues.append("component_mismatch")

    return {
        "loan_id": str(loan.id),
        "folio_number": actual or None,
        "folio_company_code": loan.folio_company_code,
        "folio_group_code": loan.folio_group_code,
        "folio_sequence": int(loan.folio_sequence or 0),
        "loan_reference": loan.loan_reference,
        "borrower_id": str(loan.borrower_id),
        "borrower_name": borrower_name,
        "borrower_identity": borrower_identity,
        "employer_group_name": group.name if group else None,
        "employer_group_code": group.code if group else None,
        "employer_name": loan.borrower.employer_name if loan.borrower else None,
        "branch_id": str(loan.branch_id) if loan.branch_id else None,
        "branch_name": branch.name if branch else None,
        "principal_amount": float(loan.principal_amount or 0),
        "amount_paid": float(loan.amount_paid or 0),
        "balance": float(loan.balance or 0),
        "status": _enum_value(loan.status),
        "origination_channel": loan.origination_channel,
        "created_at": loan.created_at.isoformat() if loan.created_at else None,
        "approved_at": loan.approved_at.isoformat() if loan.approved_at else None,
        "disbursed_at": loan.disbursed_at.isoformat() if loan.disbursed_at else None,
        "integrity_issues": integrity_issues,
    }


def build_folio_book(
    db: Session,
    *,
    context: TenantContext,
    filters: FolioBookFilters | None = None,
    skip: int = 0,
    limit: int = 500,
) -> dict[str, Any]:
    """Return a read-only, append-only view of the company's loan folio books.

    Existing folios are never renumbered and sequence gaps are never recycled. A gap is
    reported as an integrity observation only; the next number is always MAX(sequence)+1.
    """
    filters = filters or FolioBookFilters()
    loans = _loan_rows_query(db, context).all()
    rows = [_row_payload(loan) for loan in loans]

    folio_counts = Counter(row["folio_number"] for row in rows if row["folio_number"])
    sequence_counts = Counter(
        (row["folio_group_code"], row["folio_sequence"])
        for row in rows
        if row["folio_group_code"] and row["folio_sequence"] > 0
    )
    for row in rows:
        if row["folio_number"] and folio_counts[row["folio_number"]] > 1:
            row["integrity_issues"].append("duplicate_folio")
        key = (row["folio_group_code"], row["folio_sequence"])
        if key[0] and key[1] > 0 and sequence_counts[key] > 1:
            row["integrity_issues"].append("duplicate_sequence")

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row["folio_group_code"] or "UNASSIGNED")].append(row)

    sequence_books: list[dict[str, Any]] = []
    total_gap_count = 0
    for group_code, group_rows in sorted(groups.items()):
        sequences = sorted({int(row["folio_sequence"]) for row in group_rows if int(row["folio_sequence"]) > 0})
        max_sequence = sequences[-1] if sequences else 0
        present = set(sequences)
        gaps = [number for number in range(1, max_sequence + 1) if number not in present]
        total_gap_count += len(gaps)
        sample = group_rows[0]
        company_code = str(sample.get("folio_company_code") or "GEN")
        next_sequence = max_sequence + 1
        sequence_books.append({
            "group_code": group_code,
            "group_name": next((row.get("employer_group_name") for row in group_rows if row.get("employer_group_name")), None),
            "company_code": company_code,
            "loan_count": len(group_rows),
            "first_sequence": sequences[0] if sequences else None,
            "last_sequence": max_sequence or None,
            "next_sequence": next_sequence,
            "next_folio_number": f"{company_code}-{group_code}-{next_sequence:05d}",
            "gap_count": len(gaps),
            "gaps": gaps[:_MAX_REPORTED_GAPS_PER_BOOK],
            "gaps_truncated": len(gaps) > _MAX_REPORTED_GAPS_PER_BOOK,
        })

    search = (filters.search or "").strip().lower()
    group_filter = (filters.group_code or "").strip().upper()
    status_filter = (filters.status or "").strip().lower()
    branch_filter = str(filters.branch_id) if filters.branch_id else ""

    filtered = []
    for row in rows:
        if group_filter and str(row["folio_group_code"] or "").upper() != group_filter:
            continue
        if status_filter and str(row["status"] or "").lower() != status_filter:
            continue
        if branch_filter and row["branch_id"] != branch_filter:
            continue
        if search:
            haystack = " ".join(
                str(row.get(key) or "")
                for key in (
                    "folio_number",
                    "folio_group_code",
                    "loan_reference",
                    "borrower_name",
                    "borrower_identity",
                    "employer_group_name",
                    "employer_name",
                    "branch_name",
                    "status",
                )
            ).lower()
            if search not in haystack:
                continue
        filtered.append(row)

    filtered.sort(
        key=lambda row: (
            str(row.get("folio_group_code") or ""),
            int(row.get("folio_sequence") or 0),
            str(row.get("created_at") or ""),
        )
    )
    total = len(filtered)
    page_rows = filtered[skip : skip + limit]

    all_issues = Counter(issue for row in rows for issue in row["integrity_issues"])
    return {
        "summary": {
            "total_loans": len(rows),
            "sequence_book_count": len(sequence_books),
            "missing_folio_count": all_issues["missing_folio"],
            "invalid_format_count": all_issues["invalid_format"],
            "component_mismatch_count": all_issues["component_mismatch"],
            "duplicate_folio_count": all_issues["duplicate_folio"],
            "duplicate_sequence_count": all_issues["duplicate_sequence"],
            "gap_count": total_gap_count,
            "integrity_ok": not any(
                all_issues[key]
                for key in (
                    "missing_folio",
                    "invalid_format",
                    "component_mismatch",
                    "duplicate_folio",
                    "duplicate_sequence",
                )
            ),
        },
        "sequence_books": sequence_books,
        "total": total,
        "skip": skip,
        "limit": limit,
        "rows": page_rows,
    }


def folio_book_csv(payload: dict[str, Any]) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Folio Number",
        "Sequence",
        "Work Group Code",
        "Work Group",
        "Borrower",
        "National ID / Passport",
        "Loan Reference",
        "Principal",
        "Paid",
        "Balance",
        "Status",
        "Branch",
        "Created",
        "Approved",
        "Disbursed",
        "Integrity",
    ])
    for row in payload.get("rows", []):
        writer.writerow([
            row.get("folio_number") or "",
            row.get("folio_sequence") or "",
            row.get("folio_group_code") or "",
            row.get("employer_group_name") or row.get("employer_name") or "",
            row.get("borrower_name") or "",
            row.get("borrower_identity") or "",
            row.get("loan_reference") or "",
            f"{float(row.get('principal_amount') or 0):.2f}",
            f"{float(row.get('amount_paid') or 0):.2f}",
            f"{float(row.get('balance') or 0):.2f}",
            row.get("status") or "",
            row.get("branch_name") or "",
            row.get("created_at") or "",
            row.get("approved_at") or "",
            row.get("disbursed_at") or "",
            ",".join(row.get("integrity_issues") or []) or "OK",
        ])
    return output.getvalue().encode("utf-8-sig")
