from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from services.portfolio_risk_service import _first_payment_default, _loan_dpd, dpd_bucket, safe_percent


ROOT = Path(__file__).resolve().parents[2]


def installment(*, number: int, due: date, total: str, paid: str = "0", paid_at: datetime | None = None, superseded: bool = False):
    return SimpleNamespace(
        installment_number=number,
        due_date=due,
        total_due=Decimal(total),
        paid_amount=Decimal(paid),
        paid_at=paid_at,
        is_superseded=superseded,
    )


def test_dpd_bucket_boundaries_are_explicit():
    assert dpd_bucket(0) == "current"
    assert dpd_bucket(1) == "1-7"
    assert dpd_bucket(7) == "1-7"
    assert dpd_bucket(8) == "8-30"
    assert dpd_bucket(30) == "8-30"
    assert dpd_bucket(31) == "31-60"
    assert dpd_bucket(60) == "31-60"
    assert dpd_bucket(61) == "61-90"
    assert dpd_bucket(90) == "61-90"
    assert dpd_bucket(91) == "90+"


def test_dpd_uses_earliest_unpaid_non_superseded_installment():
    rows = [
        installment(number=1, due=date(2026, 8, 1), total="100", paid="100"),
        installment(number=2, due=date(2026, 8, 15), total="100", paid="25"),
        installment(number=3, due=date(2026, 9, 1), total="100", paid="0"),
        installment(number=4, due=date(2026, 7, 1), total="999", paid="0", superseded=True),
    ]
    dpd, overdue = _loan_dpd(rows, date(2026, 9, 26))
    assert dpd == 42
    assert overdue == Decimal("175.00")


def test_first_payment_default_records_late_payment_even_after_eventual_cure():
    late = installment(
        number=1,
        due=date(2026, 8, 1),
        total="100",
        paid="100",
        paid_at=datetime(2026, 8, 3, 8, 0),
    )
    on_time = installment(
        number=1,
        due=date(2026, 8, 1),
        total="100",
        paid="100",
        paid_at=datetime(2026, 8, 1, 8, 0),
    )
    assert _first_payment_default([late], date(2026, 9, 26)) is True
    assert _first_payment_default([on_time], date(2026, 9, 26)) is False


def test_safe_percent_never_invents_division_by_zero():
    assert safe_percent(10, 0) == 0.0
    assert safe_percent(25, 100) == 25.0


def test_risk_schema_stores_loan_level_daily_evidence_for_roll_rates():
    model = (ROOT / "backend" / "database" / "models" / "portfolio_risk.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend" / "alembic" / "versions" / "j4q5s6u7v801_portfolio_risk_intelligence.py").read_text(encoding="utf-8")
    assert "uq_portfolio_risk_snapshot_company_date_loan" in model
    assert "days_past_due" in model
    assert "delinquency_bucket" in model
    assert "first_payment_default" in model
    assert "is_written_off" in model
    assert "evidence_snapshot" in model
    assert 'down_revision = "i3p4r5t6u702"' in migration


def test_risk_service_covers_required_management_intelligence_without_fake_history():
    source = (ROOT / "backend" / "services" / "portfolio_risk_service.py").read_text(encoding="utf-8")
    for threshold in (1, 7, 30, 60, 90):
        assert f"for threshold in (1, 7, 30, 60, 90)" in source
    assert "first_payment_default" in source
    assert "cure_rate" in source
    assert "roll_forward_rate" in source
    assert "A second portfolio snapshot is required" in source
    assert '"vintages"' in source
    assert '"top_up_performance"' in source
    assert '"branch_risk"' in source
    assert '"product_risk"' in source
    assert '"employer_risk"' in source
    assert '"concentration"' in source
    assert '"projected_cash_flow"' in source
    assert "Collection cases explicitly marked written_off" in source


def test_portfolio_risk_api_and_ui_are_wired_into_company_command_centre():
    router = (ROOT / "backend" / "routers" / "portfolio_risk.py").read_text(encoding="utf-8")
    api_router = (ROOT / "backend" / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    page = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "portfolio-risk" / "page.tsx").read_text(encoding="utf-8")
    command = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "command-centre" / "page.tsx").read_text(encoding="utf-8")
    assert 'APIRouter(prefix="/portfolio-risk"' in router
    assert '@router.get("/overview")' in router
    assert '@router.get("/history")' in router
    assert '@router.post("/snapshot")' in router
    assert '@router.get("/export.csv")' in router
    assert "portfolio_risk.router" in api_router
    assert "Portfolio Risk Intelligence" in page
    assert "PAR 1/7/30/60/90" in page
    assert "Vintage / cohort performance" in page
    assert "/company/portfolio-risk" in command


def test_maintenance_worker_schedules_daily_risk_snapshots_after_collection_controls():
    config = (ROOT / "backend" / "database" / "config" / "config.py").read_text(encoding="utf-8")
    maintenance = (ROOT / "backend" / "docker" / "maintenance.py").read_text(encoding="utf-8")
    assert "PORTFOLIO_RISK_SNAPSHOT_ENABLED: bool = True" in config
    assert "PORTFOLIO_RISK_SNAPSHOT_HOUR: int = 0" in config
    assert "PORTFOLIO_RISK_SNAPSHOT_MINUTE: int = 45" in config
    assert "run_scheduled_portfolio_risk" in maintenance
    assert "last_portfolio_risk_snapshot_date" in maintenance
