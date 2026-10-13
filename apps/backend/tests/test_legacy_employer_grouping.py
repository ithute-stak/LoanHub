"""Employer-aware historical bank exports and four-column ingestion."""
import csv
from io import BytesIO, StringIO
from zipfile import ZipFile

from services.bank_submission_export import build_bank_submission_zip
from services.legacy_bank_import import parse_legacy_csv, parse_legacy_spreadsheet
from openpyxl import Workbook


def row(bank, account, employer, group="CIVIL"):
    return {
        "name": "Thato M", "account": account, "bank": bank,
        "branch": "060667", "group": group, "employer": employer,
        "installment": "500", "balance": "1000",
    }


def test_motheo_non_fnb_separate_but_fnb_civil_merged():
    data = [
        row("Standard Bank", "9080000000001", "Motheo"),
        row("Standard Bank", "9080000000002", "Education"),
        row("Standard Bank", "9080000000003", "Motheo"),
        row("FNB", "63000000001", "Motheo"),
        row("FNB", "63000000002", "Road Fund"),
        row("FNB", "63000000003", "Motheo", group="FORCE"),
    ]
    payload, summary = build_bank_submission_zip(data, lender_name="Batlokoa", employer_grouping=True)
    assert summary["rows"] == 6
    with ZipFile(BytesIO(payload)) as archive:
        assert set(archive.namelist()) == {
            "civil-MOTHEO.csv",
            "civil-EDUCATION.csv",
            "FNB-civil.csv",
            "FNB-force.csv",
        }
        fnb = list(csv.reader(StringIO(archive.read("FNB-civil.csv").decode())))
        assert len(fnb) == 2
        motheo = list(csv.reader(StringIO(archive.read("civil-MOTHEO.csv").decode())))
        assert len(motheo) == 2


def test_missing_employer_is_blocked_from_grouped_export():
    _, result = build_bank_submission_zip([row("Standard Bank", "9080000000001", "")],
                                          lender_name="Batlokoa", employer_grouping=True)
    assert result["rows"] == 0
    assert result["excluded"]["missing_employer"] == 1


def test_four_column_import_preserves_employer():
    data = b"Client name,Account number,Amount,Employer\nThato M,9080000000001,500,Motheo\n"
    parsed, issues = parse_legacy_csv(data, known_groups={"civil": "123"}, selected_group="CIVIL")
    assert not issues
    assert parsed[0]["employer"] == "Motheo"


def test_spreadsheet_import_preserves_employer():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Client name", "Account number", "Amount", "Employer"])
    sheet.append(["Thato M", "9080000000001", 500, "Motheo"])
    output = BytesIO()
    workbook.save(output)
    parsed, issues = parse_legacy_spreadsheet(output.getvalue(), known_groups={"civil": "123"}, selected_group="CIVIL")
    assert not issues
    assert parsed[0]["account"] == "9080000000001"
    assert parsed[0]["employer"] == "Motheo"
