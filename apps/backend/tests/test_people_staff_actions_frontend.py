from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STAFF_PANEL = ROOT / "frontend" / "components" / "people" / "staff-access-panel.tsx"


def source() -> str:
    return STAFF_PANEL.read_text(encoding="utf-8")


def test_embedded_people_workspace_exposes_staff_actions() -> None:
    text = source()

    assert 'Staff access actions' in text
    assert 'Add staff member' in text
    assert 'Export staff' in text
    assert 'onClick={() => setShowForm(true)}' in text
    assert 'onClick={handleExportStaff}' in text


def test_existing_staff_creation_dialog_remains_connected() -> None:
    text = source()

    assert 'title="Create company staff account"' in text
    assert 'await createCompanyStaffAccount({' in text
    assert 'toast.success("Staff account created")' in text


def test_staff_export_is_filtered_and_spreadsheet_safe() -> None:
    text = source()

    assert 'const rows = filteredPeople.map((person) =>' in text
    assert '/^[=+\\-@]/.test(text.trimStart())' in text
    assert 'type: "text/csv;charset=utf-8"' in text
    assert 'URL.createObjectURL(blob)' in text
    assert 'anchor.download = `${toFileSegment(companyName)}-staff-' in text


def test_export_button_is_disabled_for_empty_results() -> None:
    text = source()

    assert 'disabled={filteredPeople.length === 0}' in text
    assert 'There are no staff records to export' in text
