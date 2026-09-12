from pathlib import Path


def project_root() -> Path:
    return Path(__file__).parents[2]


def read(relative_path: str) -> str:
    return (project_root() / relative_path).read_text(encoding="utf-8")


def test_financial_institution_types_and_bank_roles_are_first_class():
    enums = read("backend/database/models/enums.py")

    for institution_type in (
        "loan_company",
        "commercial_bank",
        "microfinance_institution",
        "financial_cooperative",
        "development_finance_institution",
        "government_lending_program",
    ):
        assert institution_type in enums

    for role in (
        "credit_analyst",
        "aml_cft_officer",
        "treasury_officer",
        "data_protection_officer",
        "regulatory_reporting_officer",
        "operations_officer",
        "information_security_officer",
    ):
        assert role in enums


def test_registration_creates_a_pending_tenant_and_governance_profile():
    schema = read("backend/database/schemas/company_registration.py")
    router = read("backend/routers/company_registration.py")
    page = read("frontend/app/(auth)/register-institution/page.tsx")
    login = read("frontend/app/(auth)/login/page.tsx")

    assert "institution_type: InstitutionType" in schema
    assert "status=CompanyStatus.PENDING" in router
    assert "is_active=False" in router
    assert "InstitutionGovernanceProfile(company_id=company.id)" in router
    assert 'href="/register-institution"' in login
    assert "Commercial bank" in page
    assert "Registration does not imply regulatory approval" in page
    assert "Platform approval verifies the submitted profile" in page
    companies = read("frontend/store/slices/companiesSlice.ts")
    assert "institution_type?: InstitutionType" in companies


def test_governance_api_is_tenant_scoped_role_protected_and_audited():
    router = read("backend/routers/institution_governance.py")

    assert "Cross-institution access is not allowed" in router
    assert "company_id is required for platform oversight" in router
    assert "GOVERNANCE_WRITE_ROLES" in router
    assert "This role cannot change institution governance controls" in router
    assert 'action="institution.governance_profile_updated"' in router
    assert "changed_fields=changed_fields" in router
    assert "NON_NULLABLE_PROFILE_FIELDS" in router


def test_bank_roles_receive_deliberate_least_privilege_groups():
    access = read("backend/core/access_control.py")
    staff = read("backend/routers/company_staff.py")

    assert "UserRole.CREDIT_ANALYST" in access
    assert "UserRole.TREASURY_OFFICER" in access
    assert "UserRole.OPERATIONS_OFFICER" in access
    assert "UserRole.AML_CFT_OFFICER" in access
    assert "UserRole.DATA_PROTECTION_OFFICER" in access
    assert "UserRole.REGULATORY_REPORTING_OFFICER" in access
    assert "UserRole.INFORMATION_SECURITY_OFFICER" in access
    assert "ALLOWED_STAFF_ROLES" in staff


def test_readiness_covers_licensing_privacy_security_inclusion_and_ai():
    router = read("backend/routers/institution_governance.py")
    settings = read(
        "frontend/app/(dashboard)/company/settings/"
        "_components/institution-governance-settings.tsx"
    )

    for category in (
        '"licensing"',
        '"aml_cft"',
        '"privacy"',
        '"security"',
        '"interoperability"',
        '"digital_public_good"',
        '"inclusion"',
        '"resilience"',
        '"responsible_ai"',
    ):
        assert category in router

    assert "Governance & compliance" in read(
        "frontend/app/(dashboard)/company/settings/page.tsx"
    )
    assert "Registration does not imply regulatory approval" not in settings
    assert "This does not replace regulator approval" in settings
    assert "Human review is mandatory" in settings
    assert "Bias and fairness monitoring enabled" in settings


def test_external_identity_is_not_misrepresented_as_connected():
    router = read("backend/routers/institution_governance.py")

    identity_mapping = next(
        line for line in router.splitlines() if '("identity", "Identity"' in line
    )
    assert '"integration_ready"' in identity_mapping
    assert "authorised endpoint" in identity_mapping


def test_bank_governance_migration_follows_current_head():
    migration = read(
        "backend/alembic/versions/"
        "c2r6t8u0v132_bank_tenants_and_governance.py"
    )

    assert 'revision: str = "c2r6t8u0v132"' in migration
    assert 'down_revision: Union[str, Sequence[str], None] = "b1q5s7t9u021"' in migration
    assert '"institution_governance_profiles"' in migration
    assert '"institution_type"' in migration
    assert 'server_default="LOAN_COMPANY"' in migration
    assert '"COMMERCIAL_BANK"' in migration
    assert '"AML_CFT_OFFICER"' in migration
    assert "ALTER TYPE userrole ADD VALUE IF NOT EXISTS" in migration
    assert "enum values cannot be removed safely" in migration


def test_system_owner_has_governance_oversight_workspace():
    api = read("frontend/api/institutionGovernance.ts")
    detail = read(
        "frontend/app/(dashboard)/superadmin/companies/[id]/page.tsx"
    )

    assert "oversightConfig(companyId)" in api
    assert "Governance oversight" in detail
    assert "InstitutionGovernanceSettings" in detail
    assert "companyId={company.id}" in detail
    assert "Every saved change is audited" in detail
