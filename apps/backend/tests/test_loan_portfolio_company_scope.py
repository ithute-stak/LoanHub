from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_loan_portfolio_company_management_is_not_branch_limited() -> None:
    source = (BACKEND_ROOT / "routers" / "loans.py").read_text(encoding="utf-8")

    assert "COMPANY_MANAGEMENT_ROLES" in source
    assert (
        "if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:"
        in source
    )


def test_loan_portfolio_still_scopes_non_management_roles_to_branch() -> None:
    source = (BACKEND_ROOT / "routers" / "loans.py").read_text(encoding="utf-8")

    list_start = source.index("def list_loans(")
    get_loan_start = source.index("@router.get(\"/{loan_id}\"", list_start)
    list_source = source[list_start:get_loan_start]

    assert "ClientCompanyLoan.company_id == context.company_id" in list_source
    assert "ClientCompanyLoan.branch_id == context.branch_id" in list_source
    assert "context.role not in COMPANY_MANAGEMENT_ROLES" in list_source
