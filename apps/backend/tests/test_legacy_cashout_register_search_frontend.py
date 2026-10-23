from pathlib import Path


def test_legacy_register_searches_all_loaded_records_and_paginates_matches():
    source = (
        Path(__file__).resolve().parents[2]
        / "frontend/components/legacy-cashout/legacy-cashout-register.tsx"
    ).read_text(encoding="utf-8")
    assert "records.filter((record) =>" in source
    for field in ("folio_number", "borrower_name", "identity_number", "cell_phone", "loan_reference"):
        assert f"record.{field}" in source
    assert "filteredRecords.slice(pageStart, pageStart + PAGE_SIZE)" in source
    assert "Math.ceil(filteredRecords.length / PAGE_SIZE)" in source
    assert 'setRegisterPage(1)' in source
    assert 'No legacy cash-out entries match your search or status filter.' in source
