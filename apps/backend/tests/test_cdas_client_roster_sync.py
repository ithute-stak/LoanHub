import base64
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

import pytest
from openpyxl import Workbook

from services.cdas_client_roster_sync import (
    CdasRosterDocumentError,
    _daily_due,
    _group_document_rows,
    parse_cdas_output_document,
)
from services.cdas_client_roster_sync_scheduler import (
    _FAILURE_RETRY_SECONDS,
    _retry_delay_seconds,
)


MASERU = ZoneInfo("Africa/Maseru")


def test_csv_output_file_discovers_clients_by_employee_header():
    document = {
        "FileName": "agency-output.csv",
        "Content": (
            "EmployeeNo,EmployeeName,NationalID,Employer,DeductionAmount,DeductionStatus\n"
            "E001,Mpho Test,100100100100,Ministry A,450.50,Active\n"
            "E002,Lerato Test,200200200200,Ministry B,300.00,Active\n"
        ),
    }

    rows = parse_cdas_output_document(document)

    assert len(rows) == 2
    assert rows[0]["EmployeeNo"] == "E001"
    assert rows[1]["EmployeeName"] == "Lerato Test"


def test_base64_xlsx_output_file_is_supported_without_positional_guessing():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["CDAS agency output"])
    sheet.append(["Employee No", "First Name", "Surname", "Deduction Amount"])
    sheet.append(["P001", "Neo", "Mokoena", 725.25])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    document = {
        "FileName": "output.xlsx",
        "Content": base64.b64encode(buffer.getvalue()).decode("ascii"),
    }

    rows = parse_cdas_output_document(document)

    assert len(rows) == 1
    assert rows[0]["Employee No"] == "P001"
    assert rows[0]["Deduction Amount"] == 725.25


def test_grouping_aggregates_multiple_deduction_rows_per_employee():
    rows = [
        {
            "EmployeeNo": "E001",
            "EmployeeName": "Mpho Test",
            "DeductionAmount": "M 400.00",
            "ReferenceNo": "REF-1",
        },
        {
            "EmployeeNo": "E001",
            "EmployeeName": "Mpho Test",
            "DeductionAmount": "350.50",
            "ReferenceNo": "REF-2",
        },
    ]

    grouped = _group_document_rows(
        rows,
        year=2026,
        month=9,
        file_name="output.csv",
        content_sha256="abc",
    )

    assert set(grouped) == {"E001"}
    assert str(grouped["E001"]["total_monthly_deductions"]) == "750.50"
    assert grouped["E001"]["row_count"] == 2
    assert grouped["E001"]["references"] == {"REF-1", "REF-2"}


def test_import_stops_when_employee_number_header_is_unknown():
    document = {
        "FileName": "output.csv",
        "Content": "MysteryColumn,Name,Amount\n123,Mpho Test,500\n",
    }

    with pytest.raises(CdasRosterDocumentError, match="employee-number header"):
        parse_cdas_output_document(document)


def test_daily_roster_refresh_becomes_due_at_0345_once_per_date():
    assert not _daily_due({}, datetime(2026, 9, 24, 3, 44, tzinfo=MASERU))
    assert _daily_due({}, datetime(2026, 9, 24, 3, 45, tzinfo=MASERU))
    assert not _daily_due(
        {"last_scheduled_run_date": "2026-09-24"},
        datetime(2026, 9, 24, 18, 0, tzinfo=MASERU),
    )
    assert _daily_due(
        {"last_scheduled_run_date": "2026-09-24"},
        datetime(2026, 9, 25, 3, 45, tzinfo=MASERU),
    )


def test_failed_roster_cycle_backs_off_instead_of_retrying_each_minute():
    assert _retry_delay_seconds([], 60) == 60
    assert _retry_delay_seconds([{"status": "success"}], 60) == 60
    assert _retry_delay_seconds([{"status": "partial"}], 60) == 60
    assert _retry_delay_seconds([{"status": "failed"}], 60) == _FAILURE_RETRY_SECONDS
    assert _FAILURE_RETRY_SECONDS == 6 * 60 * 60
