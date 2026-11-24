"""Keep the company listing membership filter warning-free and tenant-scoped."""
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "routers/company.py").read_text()


def test_company_listing_uses_select_without_subquery_coercion():
    section = SOURCE.split("def list_companies(", 1)[1].split("@router.", 1)[0]
    assert "CompanyStaff.user_id == current_user.id" in section
    assert "CompanyStaff.is_active.is_(True)" in section
    assert "LoanCompany.id.in_(company_ids)" in section
    assert ".subquery()" not in section
    assert "UserRole.BORROWER" in section
