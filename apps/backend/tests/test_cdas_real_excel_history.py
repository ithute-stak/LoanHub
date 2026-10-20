"""Provider Excel export fields and amounts must survive preview and staging."""
from io import BytesIO
from openpyxl import Workbook
from services.cdas_historical_import import preview_cdas_history_file


def test_native_cdas_excel_financial_columns():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Employee No", "Employee Name", "Monthly Amount", "Total Installment",
                  "Principal Amount", "Starting Month", "Ending Month", "Policy Ref. No",
                  "User Name", "Log Time", "ACD"])
    sheet.append(["0046708", "MAMOLEMO", 1286, 3, 3858, "Aug-2026", "Oct-2026",
                  "0046708-2966", "lelefa.admin", "15/10/2026  15:21", "Delete"])
    payload = BytesIO()
    workbook.save(payload)
    result = preview_cdas_history_file(payload.getvalue(), "history.xlsx")
    assert result["valid_count"] == 1
    record = result["rows"][0]
    assert record["employee_no"] == "0046708"
    assert record["monthly_amount"] == "1286"
    assert record["principal_amount"] == "3858"
    assert record["total_installment"] == "3"
    assert record["user_name"] == "lelefa.admin"
    assert record["acd"] == "Delete"


def test_excel_history_is_evidence_not_payment():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Employee No", "Employee Name", "Monthly Amount", "Total Installment",
                  "Principal Amount", "Starting Month", "Ending Month", "Policy Ref. No",
                  "User Name", "Log Time", "ACD"])
    sheet.append(["0019336", "TEBANG", 169.44, 4, 677.76, "Nov-2026", "Feb-2027",
                  "0019336-2966", "lelefa.admin", "11/10/2026  10:40", "Add"])
    b = BytesIO()
    workbook.save(b)
    result = preview_cdas_history_file(b.getvalue(), "export.xlsx")
    assert result["persisted"] is False
    assert result["rows"][0]["monthly_amount"] == "169.44"
