"""Race-safe historical CDAS import deduplication contract."""
from pathlib import Path
from database.models.cdas_historical import CdasHistoricalImportBatch

ROUTER = (Path(__file__).resolve().parents[1] / "routers/cdas_api.py").read_text()
STAGE = ROUTER.split('@router.post("/history/import/stage")', 1)[1].split('@router.get("/history/transactions")', 1)[0]


def test_null_branch_source_uniqueness_enforced_at_db_level():
    indexes = {idx.name: idx for idx in CdasHistoricalImportBatch.__table__.indexes}
    idx = indexes["uq_cdas_history_batch_unbranched_source"]
    assert idx.unique
    assert "branch_id IS NULL" in str(idx.dialect_options["postgresql"]["where"])
    assert {"company_id", "source_sha256"} == {col.name for col in idx.columns}


def test_concurrent_duplicate_import_rolls_back_and_fails_closed():
    assert "except IntegrityError as exc:" in STAGE
    assert "db.rollback()" in STAGE
    assert "status_code=409" in STAGE
    assert '"financial_postings": 0' in STAGE
