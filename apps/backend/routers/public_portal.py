from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models.branch import CompanyBranch
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company import LoanCompany
from database.models.company_client import CompanyBorrowerAccount
from database.models.employee import EmployeeProfile
from database.models.enums import CompanyStatus, LoanStatus
from database.models.file_management import ManagedFile
from database.models.loan_offer import LoanOffer
from database.models.loan_request import LoanRequest
from database.models.reporting import GeneratedReport
from database.schemas.public_portal import PublicPlatformStats
from database.session import get_db


router = APIRouter(prefix="/public", tags=["Public"])


def _count(db: Session, model: type, *criteria: object) -> int:
    statement = select(func.count()).select_from(model)
    if criteria:
        statement = statement.where(*criteria)
    return int(db.execute(statement).scalar_one())


@router.get("/stats", response_model=PublicPlatformStats)
def public_platform_stats(
    response: Response,
    db: Session = Depends(get_db),
) -> PublicPlatformStats:
    """Return platform-wide counts that contain no customer-identifying data.

    This endpoint is deliberately unauthenticated so the public LoanHub website
    can show real activity. It publishes counts only: no names, contact details,
    tenant-level balances, loan values, documents, or per-company breakdowns.
    """

    response.headers["Cache-Control"] = "public, max-age=60, s-maxage=300"

    return PublicPlatformStats(
        approved_institutions=_count(
            db,
            LoanCompany,
            LoanCompany.status == CompanyStatus.APPROVED,
            LoanCompany.is_active.is_(True),
        ),
        active_branches=_count(db, CompanyBranch, CompanyBranch.is_active.is_(True)),
        borrower_profiles=_count(db, Borrower),
        company_client_accounts=_count(db, CompanyBorrowerAccount),
        loan_requests=_count(db, LoanRequest),
        loan_offers=_count(db, LoanOffer),
        loan_accounts=_count(db, ClientCompanyLoan),
        active_loans=_count(db, ClientCompanyLoan, ClientCompanyLoan.status == LoanStatus.ACTIVE),
        completed_loans=_count(
            db,
            ClientCompanyLoan,
            ClientCompanyLoan.status == LoanStatus.COMPLETED,
        ),
        employee_profiles=_count(db, EmployeeProfile),
        managed_files=_count(db, ManagedFile),
        generated_reports=_count(db, GeneratedReport),
        updated_at=datetime.now(timezone.utc),
    )
