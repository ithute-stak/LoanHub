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


def test_borrower_history_does_not_inherit_company_portfolio_filters():
    source = (ROOT / "frontend" / "components" / "loans" / "loan-portfolio-workspace.tsx").read_text(encoding="utf-8")
    assert 'searchParams.get("borrower")' in source
    assert 'borrowerFromUrl ? "loan-portfolio-borrower-history" : "loan-portfolio"' in source
    assert 'const folioFromUrl = borrowerFromUrl ? ""' in source
    assert 'useReduxTableField(tableKey, "search", folioFromUrl)' in source
    assert 'useReduxTableField<PortfolioFilters>(tableKey, "filters", DEFAULT_FILTERS)' in source
    reset = source.split("if (borrowerFromUrl) {", 1)[1].split("} else if", 1)[0]
    assert 'setSearch("");' in reset
    assert "setFilters(DEFAULT_FILTERS);" in reset
    assert "setPage(1);" in reset
    assert "[borrowerFromUrl, folioFromUrl]" in source
