"""Shared loan-row lock contract for financial writers and settlement revalidation.

This helper does not commit, certify external sources, or authorize settlement.
Call before taking payment/adjustment locks or mutating financial state.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.client_loan_company import ClientCompanyLoan


def lock_financial_loan(db: Session, *, company_id: UUID, loan_id: UUID):
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified company and loan scope required")
    if db.get_bind().dialect.name != "postgresql":
        raise ValueError("Financial locking requires PostgreSQL")
    # Prevent an implicit flush from writing before the row lock is obtained.
    with db.no_autoflush:
        statement = (
            select(ClientCompanyLoan)
            .where(ClientCompanyLoan.company_id == company_id,
                   ClientCompanyLoan.id == loan_id)
            .with_for_update(of=ClientCompanyLoan)
            .execution_options(populate_existing=True)
        )
        loan = db.execute(statement).scalar_one_or_none()
    if loan is None:
        raise ValueError("Scoped financial loan not found")
    return loan
