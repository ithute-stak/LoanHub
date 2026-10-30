"""Tenant-scoped persistence for arrears policy defaults and product overrides.

No live payment posting or existing loan terms are changed here.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from database.models.company_loan_settings import CompanyLoanSettings
from database.models.loan_product import LoanProduct
from .configuration import PolicySelection, read_loan_policy_snapshot, resolve_new_loan_policy


def company_policy(db: Session, *, company_id: UUID) -> PolicySelection | None:
    row = db.query(CompanyLoanSettings).filter(CompanyLoanSettings.company_id == company_id).first()
    return read_loan_policy_snapshot(row.arrears_policy) if row and row.arrears_policy else None


def set_company_policy(db: Session, *, company_id: UUID, policy: PolicySelection) -> None:
    row = db.query(CompanyLoanSettings).filter(CompanyLoanSettings.company_id == company_id).with_for_update().first()
    if row is None:
        row = CompanyLoanSettings(company_id=company_id)
        db.add(row)
    row.arrears_policy = policy.snapshot()
    db.flush()


def set_product_policy(
    db: Session, *, company_id: UUID, product_id: UUID, policy: PolicySelection | None,
) -> None:
    product = db.query(LoanProduct).filter(
        LoanProduct.id == product_id, LoanProduct.company_id == company_id,
    ).with_for_update().one_or_none()
    if product is None:
        raise LookupError("Loan product not found for company")
    product.arrears_policy_override = policy.snapshot() if policy else None
    db.flush()


def selected_policy(db: Session, *, company_id: UUID, product_id: UUID | None) -> PolicySelection:
    override = None
    if product_id is not None:
        product = db.query(LoanProduct).filter(
            LoanProduct.id == product_id, LoanProduct.company_id == company_id,
        ).one_or_none()
        if product is None:
            raise LookupError("Loan product not found for company")
        if product.arrears_policy_override:
            override = read_loan_policy_snapshot(product.arrears_policy_override)
    return resolve_new_loan_policy(
        company_default=company_policy(db, company_id=company_id),
        product_override=override,
    )
