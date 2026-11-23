from pathlib import Path


def test_client_directory_and_main_table_expose_profile_action():
    root = Path(__file__).parents[2]
    page = root / "frontend" / "app" / "(dashboard)" / "company" / "clients" / "page.tsx"
    workspace = root / "frontend" / "components" / "clients" / "company-client-directory-workspace.tsx"

    page_text = page.read_text(encoding="utf-8")
    workspace_text = workspace.read_text(encoding="utf-8")

    assert "CompanyClientProfileDialog" in page_text
    assert "setProfileClient(client)" in page_text
    assert "onViewProfile={setProfileClient}" in page_text
    assert "onViewProfile(client)" in workspace_text
    assert ">Profile</Button>" in page_text


def test_profile_dialog_contains_rating_profile_image_documents_and_history():
    root = Path(__file__).parents[2]
    component = root / "frontend" / "components" / "clients" / "company-client-profile-dialog.tsx"
    text = component.read_text(encoding="utf-8")

    assert "Payment rating" in text
    assert "Profile image" in text
    assert "Borrower documents" in text
    assert "Loan history" in text
    assert "Recent comments and legal activity" in text
    assert "uploadCompanyClientProfileImage" in text
    assert "uploadCompanyClientDocument" in text
    assert "downloadCompanyClientFile" in text


def test_government_employee_number_appears_in_client_profile_only_when_applicable():
    root = Path(__file__).parents[2]
    dialog = (root / "frontend" / "components" / "clients" / "company-client-profile-dialog.tsx").read_text(encoding="utf-8")
    cards = (root / "frontend" / "components" / "clients" / "company-client-profile-editor-cards.tsx").read_text(encoding="utf-8")
    router = (root / "backend" / "routers" / "company_clients.py").read_text(encoding="utf-8")
    schema = (root / "backend" / "database" / "schemas" / "company_clients.py").read_text(encoding="utf-8")

    assert "profile?.is_government_employee" in dialog
    assert "Employee no:" in dialog
    assert "profile.is_government_employee" in cards
    assert "Government employee no." in cards
    assert "profile.cdas_employee_number" in cards
    assert "CDASPayrollProfile.company_id == context.company_id" in router
    assert "CDASPayrollProfile.borrower_id == account.borrower_id" in router
    assert "cdas_employee_number: str | None = None" in schema


def test_government_employee_number_click_uses_existing_cdas_affordability_api():
    root = Path(__file__).parents[2]
    dialog = (root / "frontend" / "components" / "clients" / "company-client-profile-dialog.tsx").read_text(encoding="utf-8")
    cards = (root / "frontend" / "components" / "clients" / "company-client-profile-editor-cards.tsx").read_text(encoding="utf-8")

    assert 'api.post<{ ok: boolean; affordability: number }>("/cdas/employees/affordability"' in dialog
    assert 'employee_no: employeeNo' in dialog
    assert 'onClick={() => void showEmployeeAffordability()}' in dialog
    assert 'profile?.is_government_employee' in dialog
    assert 'affordabilityAmount !== null' in dialog
    assert 'affordabilityError ?' in dialog
    assert 'onViewEmployeeAffordability={(' in dialog
    assert 'onClick={onViewEmployeeAffordability}' in cards
    assert 'profile.is_government_employee' in cards
