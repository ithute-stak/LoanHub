"""Bank CSV export contract and isolation tests."""
import csv
from io import BytesIO, StringIO
from zipfile import ZipFile

from services.bank_submission_export import build_bank_submission_zip


def _record(**overrides):
    row = dict(
        name="Mosipatsi P", account="62080011400058", branch="60667",
        bank="FNB", group="FORCE", installment="1000", balance="2400",
    )
    row.update(overrides)
    return row


def _read(zip_file, name):
    return list(csv.reader(StringIO(zip_file.read(name).decode("utf-8"))))


def test_bank_submission_grouped_csv_schema_and_amount():
    payload, stats = build_bank_submission_zip([
        _record(),
        _record(name="Thato M", account="6308000869313", group="CIVIL",
                installment="500", balance="500"),
        _record(bank="Standard Lesotho Bank", group="FORCE", account="9001234567"),
        _record(bank="Standard Lesotho Bank", group="S/E", account="1001234568",
                installment="900", balance="250"),
    ], lender_name="Batlokoa Financial Services")
    with ZipFile(BytesIO(payload)) as output:
        assert set(output.namelist()) == {
            "FNB-all-groups.csv",
            "STD-force.csv",
            "LPS-s-e.csv",
        }
        rows = _read(output, "FNB-all-groups.csv")
        assert rows == [
            ["Mosipatsi", "62080011400058", "060667", "1000.00", "Batlokoa"],
            ["Thato M", "6308000869313", "060667", "500.00", "Batlokoa"],
        ]
        assert _read(output, "LPS-s-e.csv")[0][3] == "250.00"
        assert _read(output, "STD-force.csv")[0][1] == "9001234567"
    assert stats["rows"] == 4
    assert stats["files"] == 3


def test_bank_submission_excludes_settled_and_incomplete_mandates():
    payload, stats = build_bank_submission_zip([
        _record(balance="0"),
        _record(account="****0058"),
        _record(branch="1234567"),
        _record(group="UNKNOWN"),
        _record(installment="NaN"),
        _record(name="=cmd", account="6201234567"),
    ], lender_name="Batlokoa")
    with ZipFile(BytesIO(payload)) as output:
        assert _read(output, "FNB-all-groups.csv") == [
            ["cmd", "6201234567", "060667", "1000.00", "Batlokoa"]
        ]
    assert sum(stats["excluded"].values()) == 5


def test_account_prefix_routing_overrides_stale_bank_name_and_keeps_groups():
    payload, summary = build_bank_submission_zip([
        _record(account="6200000001", bank="Unknown", group="FORCE"),
        _record(account="6300000001", bank="STD", group="CIVIL"),
        _record(account="6000000001", bank="LPS", group="S/E"),
        _record(account="9000000001", bank="FNB", group="FORCE"),
        _record(account="1000000001", bank="FNB", group="CIVIL"),
        _record(account="8000000001", bank="FNB", group="S/E"),
    ], lender_name="Batlokoa Finance")
    with ZipFile(BytesIO(payload)) as output:
        assert set(output.namelist()) == {
            "FNB-all-groups.csv", "STD-force.csv",
            "LPS-civil.csv", "NB-s-e.csv",
        }
        assert len(_read(output, "FNB-all-groups.csv")) == 3
    assert summary["rows"] == 6
