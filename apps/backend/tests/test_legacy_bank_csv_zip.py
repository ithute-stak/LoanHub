"""Legacy records use the bank-submission contract and separate work groups."""
import csv
from io import BytesIO, StringIO
from zipfile import ZipFile

from services.bank_submission_export import build_bank_submission_zip


def test_manual_legacy_records_split_by_prefix_and_group():
    rows = [
        dict(name="Mosipatsi M", account="6200000001", branch="60667", bank="FNB", group="FORCE", installment="125.00", balance="125.00"),
        dict(name="Thato M", account="6300000001", branch="60667", bank="FNB", group="CIVIL", installment="55.25", balance="55.25"),
        dict(name="Khotso M", account="9000000001", branch="123", bank="STD", group="FORCE", installment="80.00", balance="80.00"),
        dict(name="Mpho M", account="1000000001", branch="543", bank="LPS", group="S/E", installment="40.00", balance="40.00"),
        dict(name="Neo M", account="8000000001", branch="7", bank="NB", group="CIVIL", installment="20.00", balance="20.00"),
    ]
    payload, stats = build_bank_submission_zip(rows, lender_name="Batlokoa Financial Services")
    with ZipFile(BytesIO(payload)) as zip_file:
        assert set(zip_file.namelist()) == {
            "FNB-all-groups.csv", "STD-force.csv", "LPS-s-e.csv", "NB-civil.csv",
        }
        fnb = list(csv.reader(StringIO(zip_file.read("FNB-all-groups.csv").decode())))
        assert len(fnb) == 2
        assert fnb[0] == ["Mosipatsi", "6200000001", "060667", "125.00", "Batlokoa"]
        std = list(csv.reader(StringIO(zip_file.read("STD-force.csv").decode())))
        assert std[0][2] == "000123"
    assert stats["rows"] == 5
