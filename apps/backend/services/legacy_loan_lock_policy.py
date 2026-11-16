"""Company-scoped legacy-loan lock policy.

No borrower identity matching. Default OFF until an administrator explicitly
enables the policy and all relevant financial mutation paths are guarded.
"""
from database.models.company_loan_settings import CompanyLoanSettings
from database.models.client_loan_company import ClientCompanyLoan
from services.legacy_loan_quarantine import exclude_legacy_captured_loans, legacy_capture_exists_for_loan


def legacy_loan_lock_enabled(db, company_id):
    row = db.query(CompanyLoanSettings.legacy_loan_lock_enabled).filter(
        CompanyLoanSettings.company_id == company_id
    ).first()
    return bool(row and row[0])


def apply_legacy_loan_visibility(db, context, query):
    if legacy_loan_lock_enabled(db, context.company_id):
        return exclude_legacy_captured_loans(query, ClientCompanyLoan)
    return query


def is_legacy_loan_locked(db, company_id, loan_id):
    if not legacy_loan_lock_enabled(db, company_id):
        return False
    return db.query(ClientCompanyLoan.id).filter(
        ClientCompanyLoan.company_id == company_id,
        ClientCompanyLoan.id == loan_id,
        legacy_capture_exists_for_loan(ClientCompanyLoan),
    ).first() is not None
