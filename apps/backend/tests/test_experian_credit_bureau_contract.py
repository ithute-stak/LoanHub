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

    assert '"has_credentials": bool(platform and has_credentials_for_environment(platform, selected_environment))' in preview
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
    assert "raw_response_encrypted" not in serializer
    assert "access_token = Column" not in model


def test_experian_is_locked_to_official_lesotho_normal_search_hosts() -> None:
    service = _read(ROOT / "services/experian_service.py")

    assert '"sandbox": "https://apis-uat.experian.co.ls:9443"' in service
    assert '"live": "https://apis.experian.co.ls:9443"' in service
    assert '"uat": "https://apis-uat.experian.co.ls:9443"' in service
    assert '"production": "https://apis.experian.co.ls:9443"' in service
    assert 'NORMAL_SEARCH_PATH = "/NormalSearchService"' in service
    assert 'PING_PATH = "/PingServer/"' in service
    assert 'PREVIOUS_ENQUIRY_PATH = "/EnqIdPrevEnqService"' in service
    assert '"username": credentials["username"]' in service
    assert '"password": credentials["password"]' in service
    assert '"client_id"' not in service
    assert '"client_secret"' not in service


def test_bureau_enquiry_requires_explicit_consent_and_identity() -> None:
    schema = _read(ROOT / "database/schemas/credit_bureau.py")
    router = _read(ROOT / "routers/credit_bureau.py")

    assert "Borrower consent must be confirmed before a bureau enquiry" in schema
    assert 'consent_confirmed=True' in router
    assert '"permissible_purpose": payload.permissible_purpose' in router
    assert 'if not identity.get("national_id") and not identity.get("passport_number")' in router
    assert '"consent_method": payload.consent_method' in router
    assert '"consent_captured_at": now.isoformat()' in router


def test_normal_search_contract_is_implemented_not_manually_reentered() -> None:
    service = _read(ROOT / "services/experian_service.py")
    platform_page = _read(FRONTEND_ROOT / "app/(dashboard)/superadmin/control/integrations/experian/page.tsx")

    assert '"product": "normal_search_v2"' in service
    assert '"origin": "LNHUB"' in service
    assert '"dll_version": "1.0"' in service
    assert '"response_mapping": {}' in service
    assert "build_normal_search_payload" in service
    assert '"searchCriteria": {' in service
    assert '"clientConsent": "Y"' in service
    assert "Experian Lesotho Normal Search contract" in platform_page
    assert "Bureau endpoint path" not in platform_page
    assert "Experian request template (JSON)" not in platform_page


def test_frontend_places_provider_credentials_only_in_platform_owner_workspace() -> None:
    company_layout = _read(FRONTEND_ROOT / "app/(dashboard)/company/origination/layout.tsx")
    company_page = _read(FRONTEND_ROOT / "app/(dashboard)/company/origination/experian/page.tsx")
    platform_page = _read(FRONTEND_ROOT / "app/(dashboard)/superadmin/control/integrations/experian/page.tsx")
    shell = _read(FRONTEND_ROOT / "components/dashboard/superadmin-shell.tsx")
    api = _read(FRONTEND_ROOT / "api/creditBureau.ts")

    assert "/company/origination/experian" in company_layout
    assert "Platform Owner" in company_page
    assert "Client Secret" not in company_page
    assert "Experian password" not in company_page
    assert "Test connection" not in company_page
    assert "Run Experian credit check" in company_page

    assert "Experian username" in platform_page
    assert "Experian password" in platform_page
    assert "Client ID" not in platform_page
    assert "Client Secret" not in platform_page
    assert "Test connection" in platform_page
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


def test_fresh_reports_are_reused_unless_staff_explicitly_force_refresh() -> None:
    schema = _read(ROOT / "database/schemas/credit_bureau.py")
    router = _read(ROOT / "routers/credit_bureau.py")
    company_page = _read(FRONTEND_ROOT / "app/(dashboard)/company/origination/experian/page.tsx")

    assert "force_refresh: bool = False" in schema
    policy_service = _read(ROOT / "services/credit_bureau_policy_service.py")
    assert "max_report_age_hours" in policy_service
    assert "timedelta(hours=max_report_age_hours)" in policy_service
    assert "if not payload.force_refresh:" in router
    assert "return _enquiry_payload(reusable)" in router
    assert "Force a new paid enquiry" in company_page
    assert "maximum report age" in company_page.lower()


def test_company_experian_policy_is_enforced_by_affordability_and_approval() -> None:
    service = _read(ROOT / "services/origination_service.py")
    policy_service = _read(ROOT / "services/credit_bureau_policy_service.py")
    approval_router = _read(ROOT / "routers/professional_lending.py")
    schema = _read(ROOT / "database/schemas/credit_bureau.py")
    company_page = _read(FRONTEND_ROOT / "app/(dashboard)/company/origination/experian/page.tsx")

    assert "company_experian_policy" in service
    assert "assert_experian_requirement" in service
    assert 'stage="affordability"' in service
    assert 'bureau_policy.get("include_bureau_commitments_in_affordability")' in service
    assert 'bureau_policy.get("bureau_debt_mode")' in service
    assert 'bureau_policy.get("decline_below_score")' in service
    assert 'bureau_policy.get("refer_below_score")' in service
    assert 'bureau_policy.get("block_defaults")' in service
    assert 'bureau_policy.get("require_identity_match")' in service
    assert '"credit_bureau": {' in service

    assert '"optional"' in schema
    assert '"before_affordability"' in schema
    assert '"before_approval"' in schema
    assert '"amount_threshold"' in schema
    assert '"selected_products"' in schema
    assert "experian_required_for_application" in policy_service
    assert 'stage="approval"' in approval_router
    assert "Optional · officer decides" in company_page
    assert "Required before approval" in company_page
    assert "Required above a loan amount" in company_page
    assert "Required for selected products" in company_page


def test_each_company_selects_its_own_experian_sandbox_or_live_mode() -> None:
    schema = _read(ROOT / "database/schemas/credit_bureau.py")
    company_router = _read(ROOT / "routers/credit_bureau_configuration.py")
    enquiry_router = _read(ROOT / "routers/credit_bureau.py")
    policy_service = _read(ROOT / "services/credit_bureau_policy_service.py")
    platform_router = _read(ROOT / "routers/platform_credit_bureau.py")
    company_page = _read(FRONTEND_ROOT / "app/(dashboard)/company/origination/experian/page.tsx")
    platform_page = _read(FRONTEND_ROOT / "app/(dashboard)/superadmin/control/integrations/experian/page.tsx")
    api = _read(FRONTEND_ROOT / "api/creditBureau.ts")

    assert 'environment: Literal["sandbox", "live"] = "sandbox"' in schema
    assert 'selected_environment = str(company_configuration.get("environment") or "sandbox")' in company_router
    assert 'row.environment = payload.configuration.environment' in company_router
    assert '"environment": selected_environment' in enquiry_router
    assert 'environment=selected_environment' in enquiry_router
    assert 'row_environment == selected_environment' in policy_service
    assert '"environment_profiles": profile_states' in platform_router
    assert "Sandbox · training and demonstrations" in company_page
    assert "Live · real credit-bureau enquiries" in company_page
    assert "Lending companies choose which mode they use" in platform_page
    assert "Credential profile" in platform_page
    assert 'environment: "sandbox" | "live";' in api
