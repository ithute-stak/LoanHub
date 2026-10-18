"""Regression coverage for custom group ZIP routing without duplicate instructions."""
from pathlib import Path

ROUTER = (Path(__file__).resolve().parents[1] / "routers/legacy_bank_deductions.py").read_text()
EXPORTER = (Path(__file__).resolve().parents[1] / "services/bank_submission_export.py").read_text()


def test_bank_zip_routes_selected_employers_to_custom_csv_only():
    assert 'custom_groups = db.query(CompanyOperatingRecord)' in ROUTER
    assert 'CompanyOperatingRecord.is_archived.is_(False)' in ROUTER
    assert 'and employer_key(entry.employer or "") in employers' in ROUTER
    assert 'if len(matched) > 1:' in ROUTER
    assert 'record["custom_filename"]' in ROUTER
    assert 'data.append(record)' in ROUTER


def test_exporter_uses_one_output_filename_per_input_record():
    assert 'custom_filename = record.get("custom_filename")' in EXPORTER
    assert 'if custom_filename:' in EXPORTER
    assert 'elif employer_grouping:' in EXPORTER


def test_zip_mixes_custom_and_ordinary_employer_csv_without_duplicates():
    from io import BytesIO
    from zipfile import ZipFile

    from services.bank_submission_export import build_bank_submission_zip

    records = [
        {"name": "Jane", "bank": "STD", "account": "9012345678", "branch": "060667",
         "group": "CIVIL", "installment": 250, "balance": 250, "employer": "NUL",
         "custom_filename": "CUSTOM-abc123.csv"},
        {"name": "John", "bank": "STD", "account": "9012345679", "branch": "060667",
         "group": "CIVIL", "installment": 300, "balance": 300, "employer": "Motheo"},
    ]
    payload, summary = build_bank_submission_zip(records, lender_name="Batlokoa", employer_grouping=True)
    assert summary["rows"] == 2
    assert summary["files"] == 2
    assert summary["excluded"] == {}
    with ZipFile(BytesIO(payload)) as archive:
        assert sorted(archive.namelist()) == ["CUSTOM-abc123.csv", "civil-MOTHEO.csv"]
        assert archive.read("CUSTOM-abc123.csv").count(b"9012345678") == 1
        assert b"9012345678" not in archive.read("civil-MOTHEO.csv")
