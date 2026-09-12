from pathlib import Path


def project_root() -> Path:
    return Path(__file__).parents[2]


def test_company_owner_account_recovery_is_company_scoped_and_owner_only():
    router = (project_root() / "backend" / "routers" / "company.py").read_text(encoding="utf-8")

    assert '@router.get("/{company_id}/owner-account"' in router
    assert '@router.patch("/{company_id}/owner-account"' in router
    assert '"/{company_id}/owner-account/temporary-password"' in router
    assert "Depends(require_platform_owner)" in router
    assert "CompanyStaff.company_id == company_id" in router
    assert "CompanyStaff.role == UserRole.COMPANY_OWNER" in router
    assert "revoke_user_sessions(db, owner.id)" in router
    assert "owner.password_hash = hash_password(temporary_password)" in router
    assert "owner.must_change_password = True" in router
    assert 'action="platform.company_owner_login_updated"' in router
    assert 'action="platform.company_owner_temporary_password_created"' in router


def test_temporary_password_is_forced_to_change_before_other_api_use():
    access_control = (project_root() / "backend" / "core" / "access_control.py").read_text(encoding="utf-8")
    auth_router = (project_root() / "backend" / "routers" / "auth.py").read_text(encoding="utf-8")
    user_model = (project_root() / "backend" / "database" / "models" / "user.py").read_text(encoding="utf-8")
    mfa_service = (project_root() / "backend" / "services" / "mfa_service.py").read_text(encoding="utf-8")

    assert "must_change_password = Column(" in user_model
    assert "PASSWORD_CHANGE_REQUIRED" in access_control
    assert '"/api/v1/auth/change-password"' in access_control
    assert '@router.post("/change-password")' in auth_router
    assert "verify_password(payload.current_password" in auth_router
    assert "current_user.must_change_password = False" in auth_router
    assert "revoke_all_sessions(db, current_user)" in auth_router
    assert 'update({"revoked": True}' in mfa_service
    assert "state.session_version = int(state.session_version or 1) + 1" in mfa_service


def test_system_owner_company_menu_exposes_edit_and_owner_login_actions():
    companies = project_root() / "frontend" / "app" / "(dashboard)" / "superadmin" / "companies"
    table = (companies / "_components" / "companies-table.tsx").read_text(encoding="utf-8")
    page = (companies / "page.tsx").read_text(encoding="utf-8")
    owner_dialog = (companies / "_components" / "company-owner-access-dialog.tsx").read_text(encoding="utf-8")
    login_page = (project_root() / "frontend" / "app" / "(auth)" / "login" / "page.tsx").read_text(encoding="utf-8")

    assert "Edit company" in table
    assert "Manage owner login" in table
    assert "CompanyEditDialog" in page
    assert "CompanyOwnerAccessDialog" in page
    assert "LoanHub never reveals the existing password" in owner_dialog
    assert "createCompanyOwnerTemporaryPassword" in owner_dialog
    assert 'result.payload.user.must_change_password' in login_page
    assert '"/change-password"' in login_page


def test_command_centre_edit_company_action_opens_and_saves():
    table = (
        project_root()
        / "frontend"
        / "components"
        / "SuperAdminCompaniesTable.tsx"
    ).read_text(encoding="utf-8")

    assert "onClick={onEdit}" in table
    assert "onEdit={() => setCompanyToEdit(company)}" in table
    assert "<CompanyEditDialog" in table
    assert "company={companyToEdit}" in table
    assert "updateCompany({" in table


def test_password_change_migration_follows_current_head():
    migration = (
        project_root()
        / "backend"
        / "alembic"
        / "versions"
        / "b1q5s7t9u021_force_temporary_password_change.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "b1q5s7t9u021"' in migration
    assert 'down_revision: Union[str, Sequence[str], None] = "f5u9w1y3z465"' in migration
    assert '"must_change_password"' in migration
