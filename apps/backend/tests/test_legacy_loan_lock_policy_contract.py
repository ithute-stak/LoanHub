"""Contract checks for a disabled-by-default, tenant-specific legacy lock."""
from pathlib import Path


def test_legacy_lock_setting_is_disabled_by_default():
    root = Path(__file__).resolve().parents[1]
    model = (root / "database/models/company_loan_settings.py").read_text()
    migration = (root / "alembic/versions/b4c5d6e7f801_legacy_loan_lock_setting.py").read_text()
    assert 'legacy_loan_lock_enabled = Column(Boolean, nullable=False, default=False, server_default="false")' in model
    assert "server_default=sa.false()" in migration


def test_policy_scopes_legacy_records_by_company_and_exact_loan():
    root = Path(__file__).resolve().parents[1]
    policy = (root / "services/legacy_loan_lock_policy.py").read_text()
    assert "CompanyLoanSettings.company_id == company_id" in policy
    assert "ClientCompanyLoan.company_id == company_id" in policy
    assert "ClientCompanyLoan.id == loan_id" in policy
    assert "legacy_capture_exists_for_loan(ClientCompanyLoan)" in policy
