from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[1]


def test_borrower_workspace_router_is_registered():
    source = (BACKEND_ROOT / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    assert "borrower_workspace," in source
    assert "borrower_workspace.router," in source


def test_borrower_workspace_resolver_preserves_tenant_and_branch_scope():
    source = (BACKEND_ROOT / "routers" / "borrower_workspace.py").read_text(encoding="utf-8")
    assert 'APIRouter(prefix="/borrower-workspace"' in source
    assert 'CompanyBorrowerAccount.company_id == context.company_id' in source
    assert 'CompanyBorrowerAccount.borrower_id == borrower_id' in source
    assert "assert_branch_scope(context, account.branch_id)" in source
    assert "require_tenant_roles(context, BORROWER_WORKSPACE_ROLES)" in source


def test_company_borrower_command_centre_integrates_controlled_workflows():
    page = (
        REPO_ROOT
        / "apps"
        / "frontend"
        / "app"
        / "(dashboard)"
        / "company"
        / "borrowers"
        / "[borrowerId]"
        / "page.tsx"
    ).read_text(encoding="utf-8")
    assert "callsApi.getClient(borrowerId)" in page
    assert "callsApi.playRecording" in page
    assert "collectionsApi.workspace" in page
    assert "collectionsApi.listActions" in page
    assert "/company/calls?borrower=" in page
    assert "Interaction wall" in page
    assert "Calls & recordings" in page


def test_phonebook_borrower_names_link_to_command_centre():
    source = (
        REPO_ROOT
        / "apps"
        / "frontend"
        / "components"
        / "calls"
        / "company-phonebook-panel.tsx"
    ).read_text(encoding="utf-8")
    assert "href={`/company/borrowers/${client.borrower_id}`}" in source
    assert "href={`/company/borrowers/${selectedClient.borrower_id}`}" in source
