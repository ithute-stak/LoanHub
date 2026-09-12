from pathlib import Path


def test_company_shell_exposes_role_guarded_global_national_id_lookup():
    root = Path(__file__).parents[2]
    shell = root / "frontend" / "components" / "portal" / "portal-shell.tsx"
    component = root / "frontend" / "components" / "clients" / "global-borrower-lookup.tsx"

    shell_text = shell.read_text(encoding="utf-8")
    component_text = component.read_text(encoding="utf-8")

    assert "GlobalBorrowerLookup" in shell_text
    assert 'mode === "company"' in shell_text
    assert "LENDING_ROLES" in shell_text
    assert "Global borrower history check" in component_text
    assert "Add new borrower" in component_text
    assert "Link existing borrower" in component_text
    assert "Open borrower record" in component_text
    assert "other lenders&apos; private notes" in component_text


def test_global_lookup_prefills_registration_and_opens_history_directory():
    root = Path(__file__).parents[2]
    page = root / "frontend" / "app" / "(dashboard)" / "company" / "clients" / "page.tsx"
    workspace = root / "frontend" / "components" / "clients" / "company-client-directory-workspace.tsx"
    utility = root / "frontend" / "utils" / "borrowerLookup.ts"

    page_text = page.read_text(encoding="utf-8")
    workspace_text = workspace.read_text(encoding="utf-8")
    utility_text = utility.read_text(encoding="utf-8")

    assert "GLOBAL_BORROWER_LOOKUP_EVENT" in page_text
    assert "national_id: nationalId" in page_text
    assert 'detail.action === "history"' in page_text
    assert "initialSearch={directoryInitialSearch}" in page_text
    assert "initialSearch?: string" in workspace_text
    assert "/company/clients?" in utility_text
