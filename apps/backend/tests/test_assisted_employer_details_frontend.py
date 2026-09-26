from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "apps" / "frontend"


def read(relative_path: str) -> str:
    return (FRONTEND / relative_path).read_text(encoding="utf-8")


def test_suggestion_search_can_persist_until_a_choice_is_committed():
    source = read("components/ui/suggestion-search.tsx")

    assert "persistOpenUntilSelection?: boolean" in source
    assert "persistOpenUntilSelection = false" in source
    assert "if (!nextOpen && persistOpenUntilSelection) return;" in source
    assert "setOpen(false);" in source


def test_assisted_employer_flow_distinguishes_sector_from_actual_employer():
    source = read("components/clients/employer-group-registration-field.tsx")

    assert "Employer details" in source
    assert "Employer sector" in source
    assert "Select employer sector" in source
    assert "Employer / work group" in source
    assert "The sector is a category; the work group is the organisation" in source
    assert "disabled={!employerSectorChosen}" in source
    assert "persistOpenUntilSelection={!selected && !newEmployerGroup}" in source


def test_changing_employer_sector_requires_employer_reselection():
    source = read("components/clients/employer-group-registration-field.tsx")

    assert "setSearch(\"\");" in source
    assert "employment_type: value" in source
    assert "employer_group_id: null" in source
    assert "employer_name: null" in source
    assert "new_employer_group: null" in source
