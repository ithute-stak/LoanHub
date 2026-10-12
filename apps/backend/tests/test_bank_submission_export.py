"""Bank CSV export contract and isolation tests."""
import csv
from io import BytesIO, StringIO
from zipfile import ZipFile

from services.bank_submission_export import build_bank_submission_zip


def _record(**overrides):
    row = dict(
        name="Mosipatsi P", account="09080011400058", branch="60667",
        bank="FNB", group="FORCE", installment="1000", balance="2400",
    )
    row.update(overrides)
    return row


def _read(zip_file, name):
    return list(csv.reader(StringIO(zip_file.read(name).decode("utf-8"))))


def test_bank_submission_grouped_csv_schema_and_amount():
    payload, stats = build_bank_submission_zip([
        _record(),
        _record(name="Thato M", account="0908000869313", group="CIVIL",
                installment="500", balance="500"),
        _record(bank="Standard Lesotho Bank", group="FORCE", account="0001234567"),
        _record(bank="Standard Lesotho Bank", group="S/E", account="0001234568",
                installment="900", balance="250"),
    ], lender_name="Batlokoa Financial Services")
    with ZipFile(BytesIO(payload)) as output:
        assert set(output.namelist()) == {
            "FNB-all-groups.csv",
            "STANDARD-LESOTHO-BANK-force.csv",
            "STANDARD-LESOTHO-BANK-s-e.csv",
        }
        rows = _read(output, "FNB-all-groups.csv")
        assert rows == [
            ["Mosipatsi", "09080011400058", "060667", "1000.00", "Batlokoa"],
            ["Thato M", "0908000869313", "060667", "500.00", "Batlokoa"],
        ]
        assert _read(output, "STANDARD-LESOTHO-BANK-s-e.csv")[0][3] == "250.00"
        assert _read(output, "STANDARD-LESOTHO-BANK-force.csv")[0][1] == "0001234567"
    assert stats["rows"] == 4
    assert stats["files"] == 3


def test_bank_submission_excludes_settled_and_incomplete_mandates():
    payload, stats = build_bank_submission_zip([
        _record(balance="0"),
        _record(account="****0058"),
        _record(branch="1234567"),
        _record(group="UNKNOWN"),
        _record(installment="NaN"),
        _record(name="=cmd", account="0001234567"),
    ], lender_name="Batlokoa")
    with ZipFile(BytesIO(payload)) as output:
        assert _read(output, "FNB-all-groups.csv") == [
            ["cmd", "0001234567", "060667", "1000.00", "Batlokoa"]
        ]
    assert sum(stats["excluded"].values()) == 5
