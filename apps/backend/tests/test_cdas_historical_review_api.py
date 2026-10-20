"""Guardrails for company-scoped, read-only historical CDAS review endpoints."""
from pathlib import Path
SOURCE = (Path(__file__).resolve().parents[1] / "routers/cdas_api.py").read_text()
SECTION = SOURCE.split('@router.get("/history/import/batches")', 1)[1].split('@router.get("/history/transactions")', 1)[0]


def test_historical_review_requires_management_and_tenant_scope():
    assert SECTION.count("_require_company_manager(context)") == 2
    assert "CdasHistoricalImportBatch.company_id == context.company_id" in SECTION
    assert "CdasHistoricalImportBatch.branch_id == context.branch_id" in SECTION
    assert "CdasHistoricalImportRow.company_id == context.company_id" in SECTION
    assert "CdasHistoricalImportRow.branch_id == context.branch_id" in SECTION
    assert "CdasHistoricalImportBatch.id == batch_id" in SECTION


def test_historical_review_is_read_only_and_paginated():
    assert "query.count()" in SECTION
    assert ".offset((page - 1) * limit).limit(limit)" in SECTION
    assert "db.commit()" not in SECTION
    assert "db.add(" not in SECTION
    assert "execute_provider_operation(" not in SECTION
