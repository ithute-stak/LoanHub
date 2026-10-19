"""Default bank ZIP must be grouped by bank branch, work group and employer."""
from io import BytesIO
from zipfile import ZipFile

from services.bank_submission_export import build_bank_submission_zip


def test_distinct_branch_group_employer_csvs_and_custom_override():
    sample = [
        {"name": "Jane", "bank": "STD", "account": "9080001845469", "branch": "060667", "group": "CIVIL", "employer": "Teacher", "installment": 500, "balance": 500},
        {"name": "Mary", "bank": "PB", "account": "1014460800011", "branch": "500100", "group": "CIVIL", "employer": "Teacher", "installment": 500, "balance": 500},
        {"name": "Lebo", "bank": "FNB", "account": "62646802208", "branch": "280061", "group": "CIVIL", "employer": "Health", "installment": 500, "balance": 500},
        {"name": "Palesa", "bank": "FNB", "account": "62646802209", "branch": "280061", "group": "CIVIL", "employer": "Teacher", "installment": 500, "balance": 500},
    ]
    payload, summary = build_bank_submission_zip(sample, lender_name="Batlokoa", employer_grouping=True)
    assert summary["rows"] == 4
    assert summary["files"] == 3
    assert not summary["excluded"]
    with ZipFile(BytesIO(payload)) as archive:
        assert sorted(archive.namelist()) == sorted([
            "STANDARD-BANK-060667-civil-TEACHER.csv", "POSTBANK-500100-civil-TEACHER.csv",
            "FNB-280061-civil.csv",
        ])


def test_fnb_work_groups_remain_distinct():
    rows = [{"name": "Jane", "bank": "FNB", "account": "62646802208", "branch": "280061", "group": group, "employer": employer, "installment": 500, "balance": 500} for group, employer in [("CIVIL", "Teacher"), ("CIVIL", "Health"), ("FORCE", "Teacher")]]
    payload, summary = build_bank_submission_zip(rows, lender_name="Batlokoa", employer_grouping=True)
    assert summary["rows"] == 3
    assert summary["files"] == 2
    with ZipFile(BytesIO(payload)) as archive:
        assert sorted(archive.namelist()) == ["FNB-280061-civil.csv", "FNB-280061-force.csv"]


def test_custom_csv_only_when_explicitly_tagged():
    row = {"name": "Jane", "bank": "STD", "account": "9080001845469",
           "branch": "060667", "group": "CIVIL", "employer": "Teacher",
           "installment": 500, "balance": 500}
    for custom, expected in [(False, "STANDARD-BANK-060667-civil-TEACHER.csv"), (True, "CUSTOM-Teachers-abc123.csv")]:
        entry = {**row}
        if custom:
            entry["custom_filename"] = "CUSTOM-Teachers-abc123.csv"
        payload, summary = build_bank_submission_zip([entry], lender_name="Batlokoa", employer_grouping=True)
        assert summary["rows"] == 1
        assert not summary["excluded"]
        with ZipFile(BytesIO(payload)) as archive:
            assert archive.namelist() == [expected]
