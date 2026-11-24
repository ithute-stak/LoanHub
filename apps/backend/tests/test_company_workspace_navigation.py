from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PORTAL_SHELL = ROOT / "apps" / "frontend" / "components" / "portal" / "portal-shell.tsx"


def test_company_navigation_groups_existing_authoritative_workspaces() -> None:
    source = PORTAL_SHELL.read_text(encoding="utf-8")

    assert 'href: "/company/command-centre"' in source
    assert 'label: "Clients & lending"' in source
    assert 'label: "Payments & finance"' in source
    assert 'label: "Workforce & HR"' in source
    assert 'label: "Company administration"' in source
    assert 'label: "Governance & reporting"' in source
    assert 'label: "Document centre"' in source

    # The old /company/files URL remains as a compatibility redirect, but must
    # not consume a second navigation item alongside the Document Centre.
    assert '{ label: "Files", href: "/company/files"' not in source
    assert '{ label: "Reports", href: "/company/reports"' not in source
    assert 'href: "/company/documents"' in source
    assert 'href: "/company/documents?tab=reports"' in source


def test_cdas_navigation_points_only_to_clean_workspace() -> None:
    source = PORTAL_SHELL.read_text(encoding="utf-8")

    assert 'label: "CDAS Workspace"' in source
    assert 'href: "/company/cdas"' in source
    assert "/company/cdas-booking" not in source
    assert "Booking Centre" not in source
    assert "Official Loan Lifecycle" not in source
    assert "Management Dashboard" not in source


def test_company_workspace_navigation_keeps_every_legacy_workflow_reachable() -> None:
    source = PORTAL_SHELL.read_text(encoding="utf-8")

    for path in (
        "/company/clients",
        "/company/marketplace",
        "/company/legacy-cashout-register",
        "/company/origination",
        "/company/loans",
        "/company/lending-operations",
        "/company/products",
        "/company/cdas",
        "/company/payments",
        "/company/cashier",
        "/company/payment-operations",
        "/company/expense-management",
        "/company/finance",
        "/company/calls",
        "/company/collections",
        "/company/hr",
        "/company/people?tab=access",
        "/company/people?tab=employees",
        "/company/performance",
        "/company/branches",
        "/company/website",
        "/company/billing",
        "/company/settings",
        "/company/control-centre",
        "/company/documents?tab=reports",
        "/company/activity",
        "/company/queries",
    ):
        assert path in source



def test_daily_issuance_report_visible_in_desktop_and_mobile_navigation() -> None:
    desktop = PORTAL_SHELL.read_text(encoding="utf-8")
    mobile = (
        ROOT / "apps" / "frontend" / "components" / "navigation"
        / "mobile-app-navigation.tsx"
    ).read_text(encoding="utf-8")
    entry = 'href: "/company/reports/daily-issuance", icon: FileChartColumn, roles: REPORTING_ROLES'
    assert entry in desktop
    assert entry in mobile
    assert desktop.index('label: "Governance & reporting"') < desktop.index(
        'label: "Daily Loan Issuance"'
    )
    assert 'activePaths: ["/company/files", "/company/reports"]' not in desktop
    assert 'activePaths: ["/company/reports", "/company/activity", "/company/queries"]' in desktop


def test_owner_consolidated_statement_uses_existing_tenant_scoped_treasury_api() -> None:
    source = (
        ROOT / "apps" / "frontend" / "app" / "(dashboard)"
        / "company" / "reports" / "branch-financial-statement" / "page.tsx"
    ).read_text(encoding="utf-8")
    mobile = (
        ROOT / "apps" / "frontend" / "components" / "navigation"
        / "mobile-app-navigation.tsx"
    ).read_text(encoding="utf-8")
    assert 'href: "/company/reports/branch-financial-statement"' in PORTAL_SHELL.read_text(encoding="utf-8")
    assert 'roles: COMPANY_MANAGEMENT_ROLES' in PORTAL_SHELL.read_text(encoding="utf-8").split(
        'href: "/company/reports/branch-financial-statement"'
    )[1].split("}", 1)[0]
    assert 'href: "/company/reports/branch-financial-statement"' in mobile
    assert 'expenseManagementApi.dashboard(businessDate)' in source
    assert 'activeRole === "company_owner" || activeRole === "company_admin"' in source
    assert "expenseManagementApi.dashboard(businessDate, " not in source
    assert "declared_closing_balance === null" in source
    assert "window.print()" in source
