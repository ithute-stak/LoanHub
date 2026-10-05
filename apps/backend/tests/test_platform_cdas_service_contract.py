"""Contracts for platform-owned CDAS subscriptions, credentials and PAYG metering."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT.parent / "frontend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_tenant_cannot_write_or_test_cdas_credentials() -> None:
    router = _read(ROOT / "routers/cdas_api.py")
    service = _read(ROOT / "services/cdas_config_service.py")

    assert '@router.put("/configuration")' in router
    assert "CDAS credentials, Item Code and provider endpoints are controlled by the LoanHub Platform Owner" in router
    assert '@router.post("/configuration/test")' in router
    assert "CDAS credential testing is controlled by the LoanHub Platform Owner." in router
    assert "raise ValueError(" in service
    assert "The Loan Company Owner may only switch the approved company between Test and Live." in service


def test_only_company_owner_can_switch_test_and_live() -> None:
    router = _read(ROOT / "routers/cdas_api.py")
    service = _read(ROOT / "services/cdas_config_service.py")
    settings = _read(FRONTEND / "app/(dashboard)/company/settings/_components/company-cdas-settings.tsx")

    assert "context.role != UserRole.COMPANY_OWNER" in router
    assert "Only the Loan Company Owner can switch CDAS between Test and Live." in router
    assert "profile.last_test_status != \"connected\"" in service
    assert 'activeRole === "company_owner"' in settings


def test_runtime_credentials_are_loaded_only_from_platform_profile() -> None:
    service = _read(ROOT / "services/cdas_config_service.py")
    platform_service = _read(ROOT / "services/platform_cdas_service.py")

    assert "get_profile(db, company_id=company_id, environment=environment)" in service
    assert "decrypt_profile_password(profile)" in service
    assert "require_approved_subscription(db, company_id=company_id)" in service
    assert "row.encrypted_credentials" not in service
    assert "CDAS_PASSWORD_PURPOSE" in platform_service


def test_successful_business_operations_are_metered_but_provider_plumbing_is_not() -> None:
    router = _read(ROOT / "routers/cdas_api.py")
    platform_service = _read(ROOT / "services/platform_cdas_service.py")

    assert "record_successful_operation(" in router
    assert 'billing_key=f"cdas-mutation:{operation.id}"' in router
    assert 'billing_key=f"cdas-read:{uuid4().hex}"' in router
    assert '"business_operation_only": True' in platform_service
    assert "reconcile_provider_operation(" in router
    reconcile_block = router.split('@router.post("/operations/{operation_id}/reconcile")', 1)[1].split('@router.post("/employees/verify")', 1)[0]
    assert "record_successful_operation(" not in reconcile_block


def test_test_environment_is_free_and_live_uses_operation_specific_pricing() -> None:
    service = _read(ROOT / "services/platform_cdas_service.py")

    assert 'live = environment == "live"' in service
    assert 'rate = _money(normalize_pricing(subscription.pricing).get(operation_type, 0)) if live else Decimal("0.00")' in service
    assert '"accrued" if live and rate > 0 else ("free_live" if live else "test")' in service
    for operation in (
        "employee_verification",
        "affordability",
        "deduction_lookup",
        "registration",
        "lifecycle",
        "modification",
        "settlement",
        "document",
    ):
        assert f'"{operation}"' in service


def test_existing_company_credentials_are_migrated_to_platform_custody() -> None:
    migration = _read(ROOT / "alembic/versions/b9d3f5g7h911_platform_cdas_service.py")

    assert 'down_revision = "a8c2e4f6g810"' in migration
    assert "INSERT INTO platform_cdas_credential_profiles" in migration
    assert "encrypted_credentials" in migration
    assert "UPDATE origination_integration_configurations" in migration
    assert "encrypted_credentials = NULL" in migration
    assert '"platform_cdas_transactions"' in migration


def test_platform_owner_console_exposes_profile_pricing_and_approval() -> None:
    router = _read(ROOT / "routers/platform_cdas.py")
    page = _read(FRONTEND / "app/(dashboard)/superadmin/control/integrations/cdas/page.tsx")

    assert 'APIRouter(prefix="/platform-owner/cdas"' in router
    assert '@router.put("/companies/{company_id}/profiles/{environment}")' in router
    assert '@router.post("/companies/{company_id}/profiles/{environment}/test")' in router
    assert '@router.post("/subscriptions/{company_id}/decision")' in router
    assert "PAYG pricing & credit controls" in page
    assert "Company-specific CDAS profile" in page
    assert "Approve subscription" in page
