from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_ai_intelligence_schema_is_advisory_and_auditable():
    model = (ROOT / "backend" / "database" / "models" / "ai_intelligence.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend" / "alembic" / "versions" / "k5r6t7v8w901_ai_intelligence_centre.py").read_text(encoding="utf-8")

    assert "AIIntelligenceRun" in model
    assert "AIIntelligenceInsight" in model
    assert "AIIntelligenceGuardrailEvent" in model
    assert "recommended_action" in model
    assert "rationale" in model
    assert "evidence" in model
    assert 'down_revision = "j4q5s6u7v801"' in migration
    assert "confidence_percent >= 0 AND confidence_percent <= 100" in migration


def test_ai_service_never_mutates_credit_or_disbursement_state():
    source = (ROOT / "backend" / "services" / "ai_intelligence_service.py").read_text(encoding="utf-8")

    assert "ClientCompanyLoan" not in source
    assert "PaymentTransaction" not in source
    assert '"advisory_only": True' in source
    assert '"human_decision_required": True' in source
    assert "recommended_action" in source
    assert "rationale" in source


def test_ai_intelligence_uses_governed_evidence_sources():
    source = (ROOT / "backend" / "services" / "ai_intelligence_service.py").read_text(encoding="utf-8")

    assert "PortfolioRiskSnapshot" in source
    assert "CollectionWorkItem" in source
    assert "CreditCommitteeCase" in source
    assert "CreditCommitteeCondition" in source
    assert "DirectLoanApplication" in source
    assert "first_payment_default" in source
    assert "days_past_due" in source
    assert "credit_committee_required" in source


def test_ai_api_has_human_feedback_and_guardrails():
    router = (ROOT / "backend" / "routers" / "ai_intelligence.py").read_text(encoding="utf-8")
    aggregate = (ROOT / "backend" / "api" / "v1" / "router.py").read_text(encoding="utf-8")

    assert 'APIRouter(prefix="/ai-intelligence"' in router
    assert '@router.post("/runs")' in router
    assert '@router.get("/insights")' in router
    assert '@router.patch("/insights/{insight_id}")' in router
    assert '"automatic_credit_decisions": False' in router
    assert '"automatic_disbursement": False' in router
    assert "ai_intelligence.router" in aggregate


def test_ai_frontend_explains_human_control_and_reasons():
    page = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "ai-intelligence" / "page.tsx").read_text(encoding="utf-8")
    api = (ROOT / "frontend" / "api" / "aiIntelligence.ts").read_text(encoding="utf-8")
    command = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "command-centre" / "page.tsx").read_text(encoding="utf-8")

    assert "Explainable operational intelligence" in page
    assert "Human-control guardrail" in page
    assert "Why this appeared" in page
    assert "Recommended human action" in page
    assert "runAIIntelligence" in api
    assert "/company/ai-intelligence" in command
