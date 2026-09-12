"""Source-contract coverage for the Experian credit-bureau integration.

These tests protect the security, tenancy and Platform Owner control invariants
when an external Experian sandbox is unavailable to CI.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT.parent / "frontend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_experian_reuses_existing_company_scoped_bureau_ledger() -> None:
    existing_model = _read(ROOT / "database/models/lending_operations.py")
    provider_model = _read(ROOT / "database/models/credit_bureau.py")
    router = _read(ROOT / "routers/credit_bureau.py")
    migration = _read(ROOT / "alembic/versions/n4d8f0a2b014_experian_credit_bureau_enquiries.py")

    assert 'class CreditBureauEnquiry(Base):' in existing_model
    assert '__tablename__ = "credit_bureau_enquiries"' in existing_model
    assert 'from database.models.lending_operations import CreditBureauEnquiry' in router
    assert 'CreditBureauEnquiry.company_id == context.company_id' in router
    assert 'CreditBureauEnquiry.application_id == application.id' in router
    assert 'DirectLoanApplication.company_id == context.company_id' in router
    assert 'assert_branch_scope(context, application.branch_id)' in router
    assert 'class CreditBureauEnquiry' not in provider_model
    assert 'class CreditBureauProviderPayload(Base):' in provider_model
    assert '__tablename__ = "credit_bureau_provider_payloads"' in provider_model
    assert 'LoanHub already created `credit_bureau_enquiries`' in migration
    assert 'op.create_table(\n        "credit_bureau_provider_payloads"' in migration
    assert 'op.create_table(\n        "credit_bureau_enquiries"' not in migration


def test_platform_owner_is_the_only_experian_secret_owner() -> None:
    platform_model = _read(ROOT / "database/models/platform_credit_bureau.py")
    platform_router = _read(ROOT / "routers/platform_credit_bureau.py")
    company_router = _read(ROOT / "routers/credit_bureau_configuration.py")
    schema = _read(ROOT / "database/schemas/credit_bureau.py")
    migration = _read(ROOT / "alembic/versions/p0a1b2c3d015_platform_experian_owner_control.py")

    assert '__tablename__ = "platform_credit_bureau_configurations"' in platform_model
    assert 'UniqueConstraint("provider", name="uq_platform_credit_bureau_provider")' in platform_model
    assert "encrypted_credentials" in platform_model
    assert "require_platform_owner" in platform_router
    assert '@router.put("/experian/configuration")' in platform_router
    assert '@router.post("/experian/test-connection")' in platform_router
    assert "encrypt_credential" in platform_router
    assert "ExperianCompanySettingsUpdate" in company_router
    assert "encrypt_credential" not in company_router
    assert "payload.credentials" not in company_router
    assert "class ExperianCompanySettingsUpdate" in schema
    assert 'down_revision = "n4d8f0a2b014"' in migration
    assert "SET encrypted_credentials = NULL" in migration
    assert "WHERE provider = 'experian'" in migration


def test_company_experian_preview_never_exposes_platform_secrets_or_mapping() -> None:
    company_router = _read(ROOT / "routers/credit_bureau_configuration.py")
    preview = company_router.split("def company_experian_preview", 1)[1].split('@router.put', 1)[0]

    assert '"has_credentials": bool(platform and platform.encrypted_credentials)' in preview
    assert '"product": platform_configuration.get("product")' in preview
    assert '"region": platform_configuration.get("region")' in preview
    assert '"encrypted_credentials"' not in preview
    assert '"bureau_endpoint_path"' not in preview
    assert '"request_template"' not in preview
    assert '"response_mapping"' not in preview


def test_bureau_requests_use_platform_connection_but_remain_company_scoped() -> None:
    router = _read(ROOT / "routers/credit_bureau.py")

    assert "def _company_integration" in router
    assert "def _platform_integration" in router
    assert 'PlatformCreditBureauConfiguration.provider == "experian"' in router
    assert "company_integration = _company_integration" in router
    assert "platform_integration = _platform_integration" in router
    assert "run_bureau_enquiry(platform_integration" in router
    assert '"connection_scope": "platform"' in router
    assert "company_id=context.company_id" in router
    assert 'CreditBureauEnquiry.company_id == context.company_id' in router


def test_raw_bureau_response_is_encrypted_and_not_returned() -> None:
    model = _read(ROOT / "database/models/credit_bureau.py")
    router = _read(ROOT / "routers/credit_bureau.py")
    service = _read(ROOT / "services/experian_service.py")
    serializer = router.split("def _enquiry_payload", 1)[1].split("def _fail_enquiry", 1)[0]

    assert "raw_response_encrypted" in model
    assert "CreditBureauProviderPayload(" in router
    assert "raw_response_encrypted=encrypt_credential" in router
    assert "CreditBureauProviderPayload" not in serializer
    assert "raw_response_encrypted" not in serializer
    assert "decrypt_credential" in service
    assert '"access_token"' in service
    assert "_TOKEN_CACHE" in service
    assert "access_token = Column" not in model


def test_experian_oauth_is_locked_to_official_emea_hosts() -> None:
    service = _read(ROOT / "services/experian_service.py")

    assert '"sandbox": "https://sandbox-eu-api.experian.com"' in service
    assert '"uat": "https://uat-eu-api.experian.com"' in service
    assert '"production": "https://eu-api.experian.com"' in service
    assert 'TOKEN_PATH = "/oauth2/v1/token"' in service
    assert '"Grant_type": "password"' in service
    assert '"client_id": credentials["client_id"]' in service
    assert '"client_secret": credentials["client_secret"]' in service
    assert 'if not path.startswith("/")' in service
    assert '"://" in path' in service


def test_bureau_enquiry_requires_explicit_consent_and_identity() -> None:
    schema = _read(ROOT / "database/schemas/credit_bureau.py")
    router = _read(ROOT / "routers/credit_bureau.py")

    assert "Borrower consent must be confirmed before a bureau enquiry" in schema
    assert 'consent_confirmed=True' in router
    assert '"permissible_purpose": payload.permissible_purpose' in router
    assert 'if not identity.get("national_id") and not identity.get("passport_number")' in router
    assert '"consent_method": payload.consent_method' in router
    assert '"consent_captured_at": now.isoformat()' in router


def test_product_contract_is_platform_configurable_not_invented() -> None:
    service = _read(ROOT / "services/experian_service.py")
    platform_page = _read(FRONTEND_ROOT / "app/(dashboard)/superadmin/control/integrations/experian/page.tsx")

    assert '"bureau_endpoint_path": ""' in service
    assert '"request_template": {}' in service
    assert '"response_mapping": {}' in service
    assert "LoanHub deliberately does not guess" in platform_page
    assert "Bureau endpoint path" in platform_page
    assert "Experian request template (JSON)" in platform_page
    assert "Response mapping (JSON)" in platform_page


def test_frontend_places_oauth_only_in_platform_owner_workspace() -> None:
    company_layout = _read(FRONTEND_ROOT / "app/(dashboard)/company/origination/layout.tsx")
    company_page = _read(FRONTEND_ROOT / "app/(dashboard)/company/origination/experian/page.tsx")
    platform_page = _read(FRONTEND_ROOT / "app/(dashboard)/superadmin/control/integrations/experian/page.tsx")
    shell = _read(FRONTEND_ROOT / "components/dashboard/superadmin-shell.tsx")
    api = _read(FRONTEND_ROOT / "api/creditBureau.ts")

    assert "/company/origination/experian" in company_layout
    assert "Platform Owner" in company_page
    assert "Client Secret" not in company_page
    assert "Developer Portal password" not in company_page
    assert "Test OAuth connection" not in company_page
    assert "Run Experian credit check" in company_page

    assert "Developer Portal username" in platform_page
    assert "Developer Portal password" in platform_page
    assert "Client ID" in platform_page
    assert "Client Secret" in platform_page
    assert "Test OAuth connection" in platform_page
    assert "/superadmin/control/integrations/experian" in shell
    assert "/platform-owner/credit-bureau/experian/configuration" in api
    assert "/platform-owner/credit-bureau/experian/test-connection" in api
    assert "/credit-bureau/applications/${applicationId}/experian" in api


def test_decision_context_compares_bureau_and_declared_debt_without_overwriting_profile() -> None:
    router = _read(ROOT / "routers/credit_bureau.py")

    assert 'BorrowerDebtObligation.monthly_installment' in router
    assert '"declared_monthly_debt"' in router
    assert '"bureau_monthly_commitments"' in router
    assert '"variance"' in router
    assert "BorrowerDebtObligation(" not in router
