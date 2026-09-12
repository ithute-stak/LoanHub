from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_company_owner_has_read_oversight_without_becoming_editor():
    governance = read(BACKEND / "routers" / "workspace_office_governance.py")
    documents = read(BACKEND / "routers" / "workspace_documents.py")

    assert "context.role == UserRole.COMPANY_OWNER" in governance
    assert "document.company_id == context.company_id" in governance
    assert "WorkspaceDocument.company_id == context.company_id" in governance
    # Governance deliberately reuses the existing _read contract. That contract
    # keeps edit/manage tied to owner/direct collaborator instead of owner oversight.
    assert "return _read(db, context, _governed_document_or_404" in governance
    assert "collaborator.permission == \"edit\"" in documents


def test_staff_visibility_is_private_by_default_but_company_public_is_explicit():
    creation = read(BACKEND / "routers" / "workspace_creation_policy.py")
    office = read(FRONTEND / "components" / "documents" / "office-workspace-home.tsx")
    organizer = read(FRONTEND / "components" / "documents" / "document-folder-organizer.tsx")

    assert 'payload.visibility == "company"' in creation
    assert 'model_copy(update={"visibility": "private"})' in creation
    assert "CLIENT_LETTER_TEMPLATE_KEYS" in creation
    assert 'return "private";' in office
    assert 'changeVisibility("company")' in organizer
    assert "Company public" in organizer
    assert "Shared with me" in organizer


def test_documents_and_spreadsheets_share_the_folder_governance_layer():
    governance = read(BACKEND / "routers" / "workspace_office_governance.py")
    spreadsheet_api = read(FRONTEND / "api" / "workspaceSpreadsheets.ts")
    office = read(FRONTEND / "components" / "documents" / "office-workspace-home.tsx")

    assert 'WorkspaceKind = Literal["document", "spreadsheet", "all"]' in governance
    assert 'startswith("spreadsheet_")' not in governance  # SQL filtering is centralized, not Python-side listing.
    assert 'func.left(WorkspaceDocument.template_key, 12) == "spreadsheet_"' in governance
    assert "fileWorkspaceItemToPersonalFolder" in spreadsheet_api
    assert 'resourceKind="spreadsheet"' in office


def test_staff_name_personal_folder_and_owner_folder_groups_are_present():
    governance = read(BACKEND / "routers" / "workspace_office_governance.py")
    organizer = read(FRONTEND / "components" / "documents" / "document-folder-organizer.tsx")

    assert "user_display_name(context.user)" in governance
    assert "WorkspaceDocumentFolder(" in governance
    assert "owner_display_name" in governance
    assert "ownerGroups" in organizer
    assert "Owner overview" in organizer
    assert "folder.can_manage" in organizer
    assert "!folder.is_personal" in organizer


def test_folder_view_choice_and_direct_document_sharing_are_exposed():
    organizer = read(FRONTEND / "components" / "documents" / "document-folder-organizer.tsx")
    api = read(FRONTEND / "api" / "workspaceDocuments.ts")

    assert 'type ViewMode = "tiles" | "list";' in organizer
    assert "localStorage.setItem(storageKey" in organizer
    assert "> Tiles<" in organizer
    assert "> List<" in organizer
    assert "addWorkspaceDocumentCollaborator" in organizer
    assert "removeWorkspaceDocumentCollaborator" in organizer
    assert "/workspace-office/sharing-directory" in api


def test_owner_read_only_details_cover_history_signatures_download_and_spreadsheets():
    governance = read(BACKEND / "routers" / "workspace_office_governance.py")
    spreadsheets = read(BACKEND / "routers" / "workspace_spreadsheets.py")

    assert '@document_router.get("/{document_id}/signatures"' in governance
    assert '@document_router.get("/{document_id}/revisions"' in governance
    assert '@document_router.get("/{document_id}/export/{format_name}")' in governance
    assert "_governed_document_or_404" in spreadsheets
    assert 'detail="You have view-only access to this spreadsheet"' in spreadsheets
