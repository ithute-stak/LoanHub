from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_company_loan_portfolio_shows_authoritative_folio_number():
    source = (
        ROOT
        / "frontend"
        / "components"
        / "loans"
        / "loan-portfolio-workspace.tsx"
    ).read_text(encoding="utf-8")

    assert ">Folio No.<" in source
    assert "loan.folio_number" in source
    assert "loan.folio_group_code" in source
    assert "loan.folio_sequence" in source
    assert 'placeholder="Loan, folio, borrower' in source
    assert "Not assigned" in source


def test_folio_number_is_searchable_in_portfolio_workspace():
    source = (
        ROOT
        / "frontend"
        / "components"
        / "loans"
        / "loan-portfolio-workspace.tsx"
    ).read_text(encoding="utf-8")

    search_block_start = source.index("const searchText = [")
    search_block_end = source.index("].filter(Boolean).join", search_block_start)
    search_block = source[search_block_start:search_block_end]
    assert "loan.folio_number" in search_block
    assert "loan.folio_company_code" in search_block
    assert "loan.folio_group_code" in search_block
