from pathlib import Path


def test_company_clients_page_uses_fullscreen_control_centre_and_case_history():
    root = Path(__file__).parents[2]
    page = root / "frontend" / "app" / "(dashboard)" / "company" / "clients" / "page.tsx"
    workspace = root / "frontend" / "components" / "clients" / "company-client-directory-workspace.tsx"

    page_text = page.read_text(encoding="utf-8")
    workspace_text = workspace.read_text(encoding="utf-8")

    assert "CompanyClientDirectoryWorkspace" in page_text
    assert "Company client control centre" in workspace_text
    assert "h-[98dvh]" in workspace_text
    assert "All client filters" in workspace_text
    assert "Payday + loans" in workspace_text
    assert "Bank last 4" in workspace_text
    assert "masked_bank_account" in workspace_text
    assert "Comments & legal" in workspace_text
    assert "Comment" in workspace_text
    assert "Legal action" in workspace_text
    assert "Complete comment & legal timeline" in workspace_text


def test_company_client_case_api_helpers_are_wired():
    root = Path(__file__).parents[2]
    api_file = root / "frontend" / "api" / "companyClients.ts"
    text = api_file.read_text(encoding="utf-8")

    assert "/company-clients/case-records" in text
    assert "/case-entries" in text
    assert "createCompanyClientCaseEntry" in text
    assert "updateCompanyClientCaseEntryStatus" in text
