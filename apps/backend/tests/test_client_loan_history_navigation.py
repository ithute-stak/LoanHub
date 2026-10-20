"""Borrower loan-history navigation must show every matching loan."""
from pathlib import Path
BASE = Path(__file__).resolve().parents[2] / "frontend/app/(dashboard)/company"
CLIENTS = (BASE / "clients/page.tsx").read_text()
LOANS = (BASE / "loans/page.tsx").read_text()

def test_client_loan_count_links_to_borrower_history():
    assert '/company/loans?borrower=${encodeURIComponent(client.borrower_id)}' in CLIENTS
    assert "view loan history for" in CLIENTS

def test_history_filters_by_borrower_not_by_loan_status():
    assert "loan.borrower_id === historyBorrowerId" in LOANS
    assert "loans={historyLoans}" in LOANS
    assert "Show all company loans" in LOANS
