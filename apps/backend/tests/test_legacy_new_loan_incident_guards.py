"""Incident regression guards: legacy status must not leak to a newer loan.

These intentionally lightweight source guards complement (not replace) live API
and database integration tests. They do not connect to production or modify data.
"""
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend"
ROOT = BACKEND.parents[1]


def test_status_and_balance_are_loan_record_fields() -> None:
    source = (BACKEND / "database/models/client_loan_company.py").read_text()
    assert '__tablename__ = "client_company_loan"' in source
    assert "amount_paid = Column(" in source
    assert "balance = Column(" in source
    assert "status = Column(" in source
    assert "borrower_id = Column(" in source


def test_legacy_capture_has_explicit_loan_link() -> None:
    source = (BACKEND / "database/models/legacy_loan_capture.py").read_text()
    assert '__tablename__ = "legacy_loan_captures"' in source
    assert "loan_id = Column(" in source
    assert 'ForeignKey("client_company_loan.id"' in source


def test_portfolio_list_scopes_before_loan_pagination() -> None:
    source = (BACKEND / "routers/loans.py").read_text()
    section = source.split("def list_loans(", 1)[1].split(
        '@router.get("/reports/loan-cash-statement.pdf")', 1
    )[0]
    assert "ClientCompanyLoan.company_id == context.company_id" in section
    assert "ClientCompanyLoan.borrower_id == borrower_id" in section
    assert section.index("ClientCompanyLoan.borrower_id == borrower_id") < section.index(".offset(skip).limit(limit)")
    assert "ClientCompanyLoan.id.desc()" in section


def test_schedule_and_repayment_use_exact_loan_identity() -> None:
    client = (FRONTEND / "api/loans.ts").read_text()
    assert 'api.get<Loan>(`/loans/${loanId}`)' in client
    assert '/loans/${loanId}/installments/${installmentId}/payments' in client
    page = (FRONTEND / "app/(dashboard)/company/loans/page.tsx").read_text()
    assert "function openSchedule(loan: Loan)" in page
    assert "setSelectedLoan(loan);" in page
    assert "getLoan(selectedLoan.id)" in page


def test_audit_uses_readonly_transaction_and_explicit_loan_links() -> None:
    script = (ROOT / "scripts/audits/legacy_new_loan_integrity_readonly.sql").read_text()
    assert "REPEATABLE READ READ ONLY" in script
    assert "ROLLBACK;" in script
    assert "linked.loan_id = l.id" in script
    assert "p.loan_id <> ri.loan_id" in script
    assert "loan_top_up_settlements" in script
    lowered = script.lower()
    # Exclude the explanatory comments before checking for write operations.
    statements = "\n".join(line for line in lowered.splitlines() if not line.lstrip().startswith("--"))
    import re
    assert not re.search(r"\b(update|delete|insert|truncate|alter|drop|create)\s+", statements)
