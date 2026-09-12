from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PORTAL_SHELL = ROOT / "apps/frontend/components/portal/portal-shell.tsx"
HR_WORKSPACE = ROOT / "apps/frontend/components/hr/hrms-workspace.tsx"


def test_workforce_navigation_is_one_role_filtered_hybrid_group() -> None:
    source = PORTAL_SHELL.read_text(encoding="utf-8")

    assert 'label: "Workforce & HR"' in source
    assert 'label: "People & access"' in source
    assert 'label: "Employee records"' in source
    assert 'label: "Performance"' in source
    assert "children?: NavItem[]" in source
    assert "filterNavigation" in source
    assert "WORKFORCE_ROLES" in source
    assert 'aria-expanded={open}' in source
    assert "sidebar-groups" in source
    assert "const targetHref = hasChildren ? item.children?.[0]?.href" in source
    assert "if (!groupsReady) return" in source

    assert '{ label: "Staff", href: "/company/staff"' not in source
    assert '{ label: "Employees", href: "/company/employees"' not in source


def test_hrms_command_centre_has_deep_linked_tabs_and_partial_failure_resilience() -> None:
    source = HR_WORKSPACE.read_text(encoding="utf-8")

    assert "safeLoad" in source
    assert "Available sections remain usable" in source
    assert '<Tabs value={preferredTab} onValueChange={selectTab}' in source
    assert 'router.replace(query ? `${pathname}?${query}` : pathname' in source
    assert 'href="/company/hr?tab=attendance"' in source
    assert 'href="/company/hr?tab=leave"' in source
    assert 'href="/company/hr?tab=payroll"' in source
    assert 'href="/company/hr?tab=recruitment"' in source
    assert 'href="/company/hr?tab=assets"' in source
    assert 'href="#attendance"' not in source
    assert "One workforce, four connected control layers" in source
