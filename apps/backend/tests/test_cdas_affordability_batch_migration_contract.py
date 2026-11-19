"""CDAS bulk batch database migration safety contracts."""
from importlib import import_module
from pathlib import Path

from database.models.cdas_affordability_batch import (
    CdasAffordabilityBatch,
    CdasAffordabilityBatchItem,
)


def test_bulk_models_are_isolated():
    assert CdasAffordabilityBatch.__tablename__ == "cdas_affordability_batches"
    assert CdasAffordabilityBatchItem.__tablename__ == "cdas_affordability_batch_items"
    assert "consent_evidence_reference" in CdasAffordabilityBatch.__table__.columns
    assert CdasAffordabilityBatch.__table__.columns["execution_enabled"].default.arg is False


def test_migration_contains_fail_closed_checks():
    revision_path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/a9c4e7b2d851_cdas_affordability_draft_batches.py"
    )
    content = revision_path.read_text(encoding="utf-8")
    assert "execution_enabled = false" in content
    assert "status IN ('draft', 'cancelled')" in content
    assert "attempt_count = 0" in content
    assert 'down_revision = "z9n3p5q7r800"' in content
