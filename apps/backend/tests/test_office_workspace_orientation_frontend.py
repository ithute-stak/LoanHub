from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OFFICE_WORKSPACE = ROOT / "frontend" / "components" / "documents" / "office-workspace-home.tsx"


def test_office_workspace_uses_focused_navigation_instead_of_stacking_everything():
    source = OFFICE_WORKSPACE.read_text(encoding="utf-8")

    assert 'type WorkspaceArea = "documents" | "spreadsheets";' in source
    assert 'type DocumentWorkspaceView = "organize" | "create";' in source
    assert 'useState<WorkspaceArea>("documents")' in source
    assert 'useState<DocumentWorkspaceView>("organize")' in source
    assert 'activeArea === "documents"' in source
    assert 'documentView === "organize"' in source
    assert "Organize & share" in source
    assert "Create & browse" in source
    assert "Spreadsheet workspace" in source
    assert '[&>main>section:first-child]:hidden' in source
