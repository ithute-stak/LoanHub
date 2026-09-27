from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from services.predictive_intelligence_service import _score_signal, risk_band


ROOT = Path(__file__).resolve().parents[2]


def test_predictive_risk_band_boundaries_are_explicit():
    assert risk_band(0) == "stable"
    assert risk_band(19.99) == "stable"
    assert risk_band(20) == "watch"
    assert risk_band(40) == "elevated"
    assert risk_band(60) == "high"
    assert risk_band(80) == "critical"
    assert risk_band(100) == "critical"


def test_dpd_worsening_creates_transparent_par30_watch_signal():
    current = SimpleNamespace(
        days_past_due=10,
        delinquency_bucket="8-30",
        first_payment_default=False,
        is_top_up=False,
    )
    previous = SimpleNamespace(days_past_due=2, delinquency_bucket="1-7")

    score, band, projected_par30, stress_bucket, reasons, action = _score_signal(current, previous, None)

    assert score == 43
    assert band == "elevated"
    assert projected_par30 is True
    assert stress_bucket == "31-60"
    assert any("DPD increased" in reason for reason in reasons)
    assert any("bucket worsened" in reason for reason in reasons)
    assert "human" in action.lower()


def test_predictive_schema_is_auditable_and_does_not_store_fake_probability():
    model = (ROOT / "backend" / "database" / "models" / "predictive_intelligence.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend" / "alembic" / "versions" / "l6s7u8w9x001_predictive_intelligence.py").read_text(encoding="utf-8")

    assert "PredictiveIntelligenceRun" in model
    assert "PredictiveLoanSignal" in model
    assert "PredictiveCashflowForecast" in model
    assert "risk_score" in model
    assert "stress_bucket_30d" in model
    assert "expected_collection" in model
    assert 'down_revision = "k5r6t7v8w901"' in migration
    assert "risk_score >= 0 AND risk_score <= 100" in migration
    assert "probability" not in model.lower()


def test_predictive_engine_uses_stored_evidence_and_remains_advisory():
    source = (ROOT / "backend" / "services" / "predictive_intelligence_service.py").read_text(encoding="utf-8")

    assert "PortfolioRiskSnapshot" in source
    assert "RepaymentInstallment" in source
    assert "CollectionWorkItem" in source
    assert "first_payment_default" in source
    assert "previous_snapshot_date" in source
    assert '"advisory_only": True' in source
    assert '"calibrated_probability_model": False' in source
    assert '"automatic_credit_decisions": False' in source
    assert '"automatic_collection_actions": False' in source
    assert "DirectLoanApplication" not in source
    assert "CreditDecision" not in source
    assert "PaymentTransaction" not in source


def test_cashflow_forecast_is_evidence_adjusted_and_labels_no_history():
    source = (ROOT / "backend" / "services" / "predictive_intelligence_service.py").read_text(encoding="utf-8")

    assert "LOOKBACK_DAYS = 90" in source
    assert 'method = "historical_collection_rate" if history_due > 0 else "contractual_no_history"' in source
    assert "expected = money(contractual * observed_rate) if history_due > 0 else money(contractual)" in source
    assert "it is not a guarantee" in source.lower()


def test_predictive_api_and_maintenance_are_company_scoped_and_scheduled_after_risk_snapshot():
    router = (ROOT / "backend" / "routers" / "predictive_intelligence.py").read_text(encoding="utf-8")
    aggregate = (ROOT / "backend" / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    maintenance = (ROOT / "backend" / "docker" / "maintenance.py").read_text(encoding="utf-8")
    config = (ROOT / "backend" / "database" / "config" / "config.py").read_text(encoding="utf-8")

    assert 'APIRouter(prefix="/predictive-intelligence"' in router
    assert '@router.get("/overview")' in router
    assert '@router.post("/runs")' in router
    assert '@router.get("/signals")' in router
    assert '"automatic_credit_decisions": False' in router
    assert "predictive_intelligence.router" in aggregate
    assert "run_scheduled_predictive_intelligence" in maintenance
    assert maintenance.index("run_scheduled_portfolio_risk") < maintenance.index("run_scheduled_predictive_intelligence")
    assert "PREDICTIVE_INTELLIGENCE_HOUR: int = 1" in config


def test_predictive_frontend_explains_forecast_limits():
    page = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "predictive-intelligence" / "page.tsx").read_text(encoding="utf-8")
    api = (ROOT / "frontend" / "api" / "predictiveIntelligence.ts").read_text(encoding="utf-8")
    command = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "command-centre" / "page.tsx").read_text(encoding="utf-8")

    assert "See portfolio pressure before it becomes a surprise" in page
    assert "not a calibrated default probability" in page
    assert "30-day stress scenario" in page
    assert "Evidence-adjusted collection outlook" in page
    assert "runPredictiveIntelligence" in api
    assert "/company/predictive-intelligence" in command
