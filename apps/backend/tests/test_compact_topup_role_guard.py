from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / "backend" / "routers" / "origination.py"
CLIENT = ROOT / "frontend" / "components" / "loans" / "compact-top-up-dialog.tsx"
PAGE = ROOT / "frontend" / "app" / "(dashboard)" / "company" / "loans" / "page.tsx"


def test_compact_topup_backend_is_restricted_to_owner_and_branch_manager():
    content = ROUTER.read_text()
    function = content.split("def create_compact_top_up(", 1)[1].split("@router.", 1)[0]
    assert "UserRole.COMPANY_OWNER" in function
    assert "UserRole.BRANCH_MANAGER" in function
    assert 'payload.application_type != "top_up"' in function
    assert "return create_application(" in function


def test_compact_topup_uses_server_authorized_endpoint_not_generic_application():
    client = CLIENT.read_text()
    page = PAGE.read_text()
    assert "originationApi.createCompactTopUp(" in client
    assert 'activeRole === "company_owner"' in page
    assert 'activeRole === "branch_manager"' in page
    assert "setTopUpLoan(selectedLoan)" in page
    assert "router.push(`/company/origination/new?application=${applicationId}`)" in page


def test_topup_flow_does_not_mark_new_loan_approved():
    source = ROUTER.read_text().split("def create_compact_top_up(", 1)[1].split("@router.", 1)[0]
    assert "status = \"approved\"" not in source
    assert "disburse" not in source
