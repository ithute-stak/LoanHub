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
