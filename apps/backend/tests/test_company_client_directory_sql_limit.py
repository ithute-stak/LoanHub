"""Guard optimized unfiltered client directory loading against full table scans."""
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "routers" / "company_clients.py").read_text()


def test_unfiltered_directory_limits_sql_before_portfolio_summary_generation():
    start = SOURCE.index("def list_company_clients(")
    end = SOURCE.index("@router.get(\"/portfolio-insights\"", start)
    body = SOURCE[start:end]
    assert "needs_summary_filter = any((" in body
    assert "ordered_query.limit(limit).all()" in body
    assert "if needs_summary_filter" in body
    assert "else ordered_query.limit(limit).all()" in body
    assert body.index("ordered_query.limit(limit).all()") < body.index(
        "_directory_summaries(db, context=context, accounts=accounts)"
    )


def test_summary_dependent_filters_do_not_use_prelimit_path():
    start = SOURCE.index("def list_company_clients(")
    end = SOURCE.index("@router.get(\"/portfolio-insights\"", start)
    body = SOURCE[start:end]
    for parameter in (
        "loan_status is not None",
        "employment_status is not None",
        "opening_fee_status is not None",
        "has_bank_account is not None",
        "has_loan is not None",
        "overdue_only",
        "due_within_days is not None",
        "salary_due_within_days is not None",
    ):
        assert parameter in body
    assert "ordered_query.all()" in body
