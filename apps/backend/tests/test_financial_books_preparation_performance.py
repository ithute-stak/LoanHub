from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROUTER = ROOT / "apps" / "backend" / "routers" / "accounting.py"
WORKSPACE = ROOT / "apps" / "frontend" / "components" / "accounting" / "financial-books-workspace.tsx"


def test_financial_books_summary_path_avoids_per_account_n_plus_one_queries() -> None:
    source = ROUTER.read_text(encoding="utf-8")

    assert "def _ledger_book_summary_data(" in source
    assert ".group_by(JournalLine.account_id)" in source
    assert "opening_by_account" in source
    assert "period_by_account" in source
    assert "else _ledger_book_summary_data(" in source


def test_interactive_financial_books_request_is_summary_first() -> None:
    source = WORKSPACE.read_text(encoding="utf-8")

    assert "includeLedgerDetail: false" in source
    assert "void loadControls();" in source
    assert "void loadBooks();\\n      void loadControls();" not in source
    assert "Prepare books" in source
