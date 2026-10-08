from __future__ import annotations

import base64
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import Workbook

from services.cdas_roster_intelligence import (
    DAILY_SYNC_TIME,
    build_roster_snapshot,
    parse_cdas_roster_document,
)


MASERU = ZoneInfo("Africa/Maseru")
ROOT = Path(__file__).resolve().parents[3]
MANAGE_PAGE = ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "cdas" / "manage" / "page.tsx"
MAIN = ROOT / "apps" / "backend" / "main.py"
ROUTER = ROOT / "apps" / "backend" / "routers" / "cdas_api.py"
SERVICE = ROOT / "apps" / "backend" / "services" / "cdas_roster_intelligence.py"
SCHEDULER = ROOT / "apps" / "backend" / "services" / "cdas_roster_intelligence_scheduler.py"


def test_csv_roster_is_normalised_by_employee_number() -> None:
    document = {
        "FileName": "output.csv",
        "Content": (
            "EmployeeNo,EmployeeName,Employer,DeductionAmount,DeductionStatus\n"
            "E001,Mpho Test,Ministry A,450.50,Active\n"
            "E001,Mpho Test,Ministry A,100.00,Active\n"
            "E002,Lerato Test,Ministry B,300.00,Approved\n"
        ),
    }

    rows, digest = parse_cdas_roster_document(document)
    snapshot = build_roster_snapshot(rows)

    assert len(digest) == 64
    assert snapshot["employee_count"] == 2
    assert snapshot["total_monthly_deductions"] == "850.50"
    assert snapshot["employees"][0]["employee_number"] == "E001"
    assert snapshot["employees"][0]["monthly_deductions"] == "550.50"


def test_xlsx_roster_discovers_header_without_column_guessing() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["CDAS report"])
    sheet.append(["Employee No", "First Name", "Surname", "Deduction Amount"])
    sheet.append(["P001", "Neo", "Mokoena", 725.25])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()

    rows, _ = parse_cdas_roster_document(
        {
            "FileName": "output.xlsx",
            "Content": base64.b64encode(buffer.getvalue()).decode("ascii"),
        }
    )

    assert rows[0]["Employee No"] == "P001"
    assert rows[0]["Deduction Amount"] == 725.25


def test_roster_sync_uses_current_platform_controls_and_daily_dedupe() -> None:
    source = SERVICE.read_text(encoding="utf-8")

    assert 'operation_type="document"' in source
    assert 'snapshot_kind": "cdas_roster"' in source
    assert "assert_live_credit_available(" in source
    assert "get_company_cdas_client(" in source
    assert "record_successful_operation(" in source
    assert "billing_key=key" in source
    assert "MAX_SNAPSHOT_EMPLOYEES = 5000" in source
    assert DAILY_SYNC_TIME.hour == 3
    assert DAILY_SYNC_TIME.minute == 45


def test_roster_sync_scheduler_is_cross_worker_safe_and_production_wired() -> None:
    scheduler = SCHEDULER.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")

    assert "pg_try_advisory_lock" in scheduler
    assert "pg_advisory_unlock" in scheduler
    assert "start_cdas_roster_intelligence_scheduler" in main
    assert "stop_cdas_roster_intelligence_scheduler" in main
    assert "if not settings.SANDBOX_MODE" in main


def test_roster_intelligence_is_exposed_without_raw_provider_forms() -> None:
    router = ROUTER.read_text(encoding="utf-8")
    page = MANAGE_PAGE.read_text(encoding="utf-8")

    assert '@router.get("/roster-intelligence")' in router
    assert '@router.post("/roster-intelligence/refresh")' in router
    assert 'api.get<RosterResponse>("/cdas/roster-intelligence")' in page
    assert 'api.post("/cdas/roster-intelligence/refresh")' in page
    assert "CDAS roster intelligence" in page
    assert "Monthly deductions" in page
