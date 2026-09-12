from io import BytesIO

from openpyxl import load_workbook
import pytest

from routers.workspace_spreadsheets import router
from services.workspace_spreadsheet_service import (
    SpreadsheetValidationError,
    blank_workbook,
    export_csv,
    export_xlsx,
    import_workbook,
    normalize_workbook,
    workbook_plain_text,
)


def test_blank_budget_workbook_exports_formulas_and_styles():
    workbook = blank_workbook(template="budget")
    content = export_xlsx(workbook)

    loaded = load_workbook(BytesIO(content), data_only=False)
    sheet = loaded["Sheet1"]
    assert sheet["A1"].value == "Category"
    assert sheet["A1"].font.bold is True
    assert sheet["D2"].value == "=B2-C2"
    assert sheet["E2"].value == "=IF(B2=0,0,D2/B2)"
    assert sheet["E2"].number_format == "0.00%"


def test_xlsx_import_round_trip_keeps_multiple_sheets_and_formula():
    source = blank_workbook(template="cashbook")
    source["sheets"].append(
        {
            "id": "sheet-2",
            "name": "Summary",
            "row_count": 40,
            "column_count": 12,
            "cells": {"A1": {"value": "Total"}, "B1": {"formula": "=SUM(Sheet1!D2:D10)", "value": "=SUM(Sheet1!D2:D10)"}},
            "column_widths": {},
            "row_heights": {},
            "merges": [],
            "freeze_panes": None,
        }
    )
    source["active_sheet"] = "Summary"

    imported = import_workbook(export_xlsx(source), "cashbook.xlsx")
    assert [sheet["name"] for sheet in imported["sheets"]] == ["Sheet1", "Summary"]
    assert imported["active_sheet"] == "Summary"
    assert imported["sheets"][1]["cells"]["B1"]["formula"] == "=SUM(Sheet1!D2:D10)"
    assert "Summary" in workbook_plain_text(imported)


def test_csv_import_can_be_edited_and_exported():
    imported = import_workbook(b"Name,Amount\nAlice,1200\nBob,800\n", "clients.csv")
    sheet = imported["sheets"][0]
    assert sheet["cells"]["A2"]["value"] == "Alice"
    assert sheet["cells"]["B3"]["value"] == "800"

    sheet["cells"]["B3"] = {"value": 850}
    exported = export_csv(imported).decode("utf-8-sig")
    assert "Bob,850" in exported


def test_workbook_limits_reject_oversized_cell_reference():
    payload = blank_workbook()
    payload["sheets"][0]["cells"]["A5001"] = {"value": "too far"}
    with pytest.raises(SpreadsheetValidationError):
        normalize_workbook(payload)


def test_spreadsheet_router_exposes_create_import_save_export_and_publish():
    methods_by_path = {
        route.path: set(route.methods or set())
        for route in router.routes
        if hasattr(route, "path")
    }
    assert "POST" in methods_by_path["/workspace-spreadsheets"]
    assert "POST" in methods_by_path["/workspace-spreadsheets/import"]
    assert "PATCH" in methods_by_path["/workspace-spreadsheets/{document_id}"]
    assert "GET" in methods_by_path["/workspace-spreadsheets/{document_id}/export/{format_name}"]
    assert "POST" in methods_by_path["/workspace-spreadsheets/{document_id}/publish"]
