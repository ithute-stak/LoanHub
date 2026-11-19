"""Non-routed tenant business-record authorization for a LoanHub loan PDF.

An association in ManagedFile metadata is never sufficient to prove that the
referenced loan exists or belongs to the same company. This adapter verifies
the actual ClientCompanyLoan row before delegating to the protected source PDF
resolver and immutable staging pipeline. It does not assert that the PDF text
correctly represents the loan; that still requires trusted generator binding.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from core.access_control import COMPANY_MANAGEMENT_ROLES, TenantContext, require_tenant_roles
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus
from services.document_issuance_source_provenance import stage_authorized_managed_pdf_source


def require_authorized_loan_document_record(
    *, db: Session, context: TenantContext, loan_id: UUID,
) -> ClientCompanyLoan:
    """Require an approved, same-tenant loan with a real borrower reference."""
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    if (context.is_platform_admin or not isinstance(context.company_id, UUID)
            or context.company is None or context.company.id != context.company_id
            or context.user is None or context.staff is None
            or not isinstance(loan_id, UUID)):
        raise PermissionError("Verified tenant and loan identity required")
    loan = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.id == loan_id,
        ClientCompanyLoan.company_id == context.company_id,
        ClientCompanyLoan.status.in_([
            LoanStatus.APPROVED, LoanStatus.ACTIVE,
            LoanStatus.COMPLETED, LoanStatus.DEFAULTED,
        ]),
        ClientCompanyLoan.approved_at.isnot(None),
    ).one_or_none()
    if (loan is None or loan.id != loan_id
            or loan.company_id != context.company_id
            or not isinstance(loan.borrower_id, UUID)
            or loan.status not in (
                LoanStatus.APPROVED, LoanStatus.ACTIVE,
                LoanStatus.COMPLETED, LoanStatus.DEFAULTED,
            )
            or loan.approved_at is None):
        raise PermissionError("Approved tenant-owned loan required for PDF source")
    return loan


def stage_authorized_loan_pdf_source(
    *, db: Session, context: TenantContext, loan_id: UUID,
    source_file_id: UUID, trusted_verification_origin: str, store,
    stamp_configuration_version: int,
):
    """Staging-only adapter for a source linked to an actual approved loan.

    Does not validate rendered contract terms; no public route invokes this.
    """
    require_authorized_loan_document_record(
        db=db, context=context, loan_id=loan_id,
    )
    return stage_authorized_managed_pdf_source(
        db=db, context=context, source_file_id=source_file_id,
        source_type="client_company_loan", source_id=str(loan_id),
        trusted_verification_origin=trusted_verification_origin, store=store,
        stamp_configuration_version=stamp_configuration_version,
    )
