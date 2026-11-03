"""Regression guards for tenant-scoped borrower history retrieval."""
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = BACKEND_ROOT.parent / "frontend"


def test_borrower_history_filters_before_pagination() -> None:
    source = (BACKEND_ROOT / "routers" / "loans.py").read_text(encoding="utf-8")
    start = source.index("def list_loans(")
    end = source.index('@router.get("/reports/loan-cash-statement.pdf")', start)
    handler = source[start:end]
    assert "borrower_id: UUID | None = Query(default=None)" in handler
    assert "ClientCompanyLoan.company_id == context.company_id" in handler
    assert "ClientCompanyLoan.branch_id == context.branch_id" in handler
    assert handler.index("ClientCompanyLoan.borrower_id == borrower_id") < handler.index(".offset(skip).limit(limit)")
    assert "ClientCompanyLoan.id.desc()" in handler


def test_frontend_requests_all_borrower_history_pages() -> None:
    client = (FRONTEND_ROOT / "api" / "loans.ts").read_text(encoding="utf-8")
    start = client.index("export async function listBorrowerLoans(")
    end = client.index("export async function getLoan(", start)
    helper = client[start:end]
    assert "borrower_id: borrowerId, skip, limit: pageSize" in helper
    assert "if (data.length < pageSize) return loans;" in helper
    assert "loan.borrower_id !== borrowerId" in helper


def test_borrower_history_does_not_silently_show_failed_request_as_empty() -> None:
    page = (FRONTEND_ROOT / "app" / "(dashboard)" / "company" / "loans" / "page.tsx").read_text(encoding="utf-8")
    assert "listBorrowerLoans(historyBorrowerId)" in page
    assert "setBorrowerHistoryError(getErrorMessage(" in page
    assert "Unable to load borrower loans" in page
    assert "borrowerHistoryLoading ?" in page
