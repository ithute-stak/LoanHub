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
