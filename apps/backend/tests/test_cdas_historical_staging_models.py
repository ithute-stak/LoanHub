"""Historical CDAS staging schema is isolated from financial payment tables."""
from database.models.cdas_historical import CdasHistoricalImportBatch, CdasHistoricalImportRow


def test_staging_models_are_separate_from_payment_and_mandates():
    assert CdasHistoricalImportBatch.__tablename__ == "cdas_historical_import_batches"
    assert CdasHistoricalImportRow.__tablename__ == "cdas_historical_import_rows"
    assert "source_sha256" in CdasHistoricalImportBatch.__table__.columns
    assert "reconciliation_status" in CdasHistoricalImportRow.__table__.columns
    assert "payment_transaction_id" not in CdasHistoricalImportRow.__table__.columns
    assert "loan_id" not in CdasHistoricalImportRow.__table__.columns
