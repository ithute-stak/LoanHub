"""Preserve archival CDAS evidence but retire origination affordability routes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_origination_affordability_api_is_removed():
    router = (ROOT / "routers/origination.py").read_text(encoding="utf-8")
    assert '@router.post("/applications/{application_id}/assess")' not in router
    assert '@router.post("/assessments/{assessment_id}/override")' not in router
    assert "async def assess_application(" not in router
    assert "def submit_application(" in router
    assert "A positive affordability assessment is required" not in router


def test_historical_affordability_rows_remain_readable_for_migration_safety():
    service = (ROOT / "services/origination_service.py").read_text(encoding="utf-8")
    assert "def calculate_affordability(" in service
    assert "AffordabilityAssessment(" in service
