from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "apps" / "frontend"


STICKY_TOOLBAR_CONSUMERS = {
    "app/(dashboard)/borrower/requests/page.tsx": "Loan request history search",
    "app/(dashboard)/company/branches/page.tsx": "Branch directory search",
    "app/(dashboard)/company/cashier/page.tsx": "Cashier loan and borrower search",
    "app/(dashboard)/company/clients/page.tsx": "Company client search and filters",
    "app/(dashboard)/company/collections/page.tsx": "Collections recovery queue search and filters",
    "app/(dashboard)/company/expense-management/page.tsx": "Money book search and direction filters",
    "app/(dashboard)/company/marketplace/_components/internal-applications-workspace.tsx": "Internal application search and status filters",
    "app/(dashboard)/company/products/page.tsx": "Loan product search",
    "app/(dashboard)/superadmin/companies/_components/companies-table.tsx": "Company management search and filters",
    "app/(dashboard)/superadmin/companies/branches/_components/branch-table.tsx": "Branch directory search and filters",
    "app/(dashboard)/superadmin/company-admins/_components/adminTable.tsx": "Company administrator search and filters",
    "app/(dashboard)/superadmin/employees/page.tsx": "Platform employee search",
    "app/(dashboard)/superadmin/loans/page.tsx": "Platform loan request search and filters",
    "app/(dashboard)/superadmin/plans/_components/plans-management.tsx": "Subscription plan search and filters",
    "components/loans/loan-portfolio-workspace.tsx": "Company loan portfolio search and quick filters",
    "components/hr/hrms-workspace.tsx": "Workforce workspace navigation",
}


def read(relative_path: str) -> str:
    return (FRONTEND / relative_path).read_text(encoding="utf-8")


def test_sticky_toolbar_uses_css_fallback_and_overflow_safe_fixed_mode():
    source = read("components/ui/sticky-filter-bar.tsx")

    assert 'floating ? "fixed" : "sticky"' in source
    assert "ResizeObserver" in source
    assert "IntersectionObserver" in source
    assert "geometry.height" in source
    assert "window.addEventListener(\"scroll\", scheduleMeasure, true)" in source
    assert 'data-loanhub-sticky-toolbar="true"' in source
    assert "env(safe-area-inset-top)" in source
    assert "useWorkspaceFullscreen" in source


def test_all_directory_and_register_toolbars_use_shared_floating_component():
    for relative_path, aria_label in STICKY_TOOLBAR_CONSUMERS.items():
        source = read(relative_path)
        assert "StickyFilterBar" in source, relative_path
        assert "<StickyFilterBar" in source, relative_path
        assert f'ariaLabel="{aria_label}"' in source, relative_path


def test_hr_workspace_uses_navigation_landmark_for_sticky_tabs():
    source = read("components/hr/hrms-workspace.tsx")

    assert 'landmarkRole="navigation"' in source
    assert 'ariaLabel="Workforce workspace navigation"' in source


def test_existing_company_client_rollout_remains_enabled():
    source = read("app/(dashboard)/company/clients/page.tsx")

    assert 'ariaLabel="Company client search and filters"' in source
    assert 'className="overflow-visible rounded-3xl' in source
    assert 'CardContent className="overflow-hidden rounded-b-3xl p-0"' in source
