"""Historical CDAS staging must be isolated from financial posting."""
from pathlib import Path
API = (Path(__file__).resolve().parents[1] / "routers/cdas_api.py").read_text()
STAGE = API.split('@router.post("/history/import/stage")', 1)[1].split('@router.get("/history/transactions")', 1)[0]


def test_stage_requires_authorized_complete_csv():
    assert "_require_company_manager(context)" in STAGE
    assert 'preview["invalid_count"] or not preview["valid_count"]' in STAGE
    assert "source_sha256 == fingerprint" in STAGE
    assert "CdasHistoricalImportBatch.branch_id" in STAGE


def test_stage_only_writes_staging_and_audit_tables():
    assert "db.add(CdasHistoricalImportBatch(" not in STAGE
    assert "db.add(CdasHistoricalImportRow(" in STAGE
    assert 'action="cdas.historical_import_staged"' in STAGE
    assert '"financial_postings": 0' in STAGE
    for forbidden in ("db.add(PaymentTransaction(", "db.add(CDASDeductionMandate(", "execute_provider_operation("):
        assert forbidden not in STAGE
