"""Regression coverage for literal raw-regex escaping in bank submission exports."""
from io import BytesIO
from zipfile import ZipFile

from services.bank_submission_export import build_bank_submission_zip


def test_custom_csv_filename_accepts_only_literal_csv_extension():
    row = {
        "name": "Mokete T", "account": "60123456789", "branch": "280061",
        "bank": "FNB", "group": "FORCE", "installment": "100", "balance": "100",
    }
    payload, summary = build_bank_submission_zip(
        [{**row, "custom_filename": "CUSTOM-TEAM_1.csv"}],
        lender_name="Batlokoa Financial Services",
    )
    with ZipFile(BytesIO(payload)) as archive:
        assert archive.namelist() == ["CUSTOM-TEAM_1.csv"]
    assert summary["rows"] == 1

    payload, summary = build_bank_submission_zip(
        [{**row, "custom_filename": "CUSTOM-TEAM_1Xcsv"}],
        lender_name="Batlokoa Financial Services",
    )
    with ZipFile(BytesIO(payload)) as archive:
        assert archive.namelist() == []
    assert summary["excluded"] == {"invalid_custom_group": 1}


def test_employer_grouping_normalizes_whitespace():
    row = {
        "name": "Mokete T", "account": "60123456789", "branch": "280061",
        "bank": "FNB", "group": "FORCE", "installment": "100", "balance": "100",
        "employer": "  Ministry    of   Health  ",
    }
    payload, summary = build_bank_submission_zip(
        [row], lender_name="Batlokoa Financial Services", employer_grouping=True,
    )
    with ZipFile(BytesIO(payload)) as archive:
        assert "FNB-280061-force.csv" in archive.namelist()
    assert summary["rows"] == 1
