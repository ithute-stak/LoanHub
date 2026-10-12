from services.legacy_bank_import import parse_legacy_csv


def test_three_column_import_selected_work_group_and_missing_branch():
    data = b"Client name,Account number,Amount\nMamothusi Mohapi,9080004214532,2500\n"
    records, issues = parse_legacy_csv(data, known_groups={"civil": "00000000-0000-0000-0000-000000000001"}, selected_group="CIVIL")
    assert issues == []
    assert len(records) == 1
    assert records[0]["name"] == "Mamothusi Mohapi"
    assert records[0]["branch"] == ""
    assert str(records[0]["amount"]) == "2500"


def test_three_column_import_without_selected_group_rejected():
    records, issues = parse_legacy_csv(b"Mamothusi Mohapi,9080004214532,2500\n", known_groups={})
    assert not records
    assert issues[0]["reason"] == "Expected 5 columns"
