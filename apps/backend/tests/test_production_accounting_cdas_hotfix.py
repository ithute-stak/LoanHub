from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUDGET = ROOT / "apps" / "backend" / "services" / "cdas_request_budget.py"
MIGRATION = ROOT / "apps" / "backend" / "alembic" / "versions" / "g4i8k0m2n456_repair_paymentpurpose_labels.py"


def test_cdas_budget_uses_platform_credential_profile_first() -> None:
    source = BUDGET.read_text(encoding="utf-8")
    assert "PlatformCdasCredentialProfile" in source
    assert "PlatformCdasCredentialProfile.company_id == company_id" in source
    assert "PlatformCdasCredentialProfile.environment == environment" in source
    assert "if profile is not None" in source
    assert "Compatibility fallback for pre-migration installations only" in source


def test_paymentpurpose_migration_repairs_sqlalchemy_member_names() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for label in (
        "BORROW_REQUEST_FEE",
        "PLATFORM_TRANSACTION_CHARGE",
        "PLATFORM_CLAIM_SETTLEMENT",
        "DIRECT_DEBIT",
    ):
        assert label in source
    assert 'down_revision: Union[str, Sequence[str], None] = "f3h7j9l1m345"' in source
    assert "ADD VALUE IF NOT EXISTS" in source
