"""Regression guards for unified CDAS reporting safety."""
from pathlib import Path

api = (Path(__file__).resolve().parents[1] / "routers/cdas_api.py").read_text()
log = api.split('@router.get("/history/transactions")', 1)[1].split('def _filtered_history_export(', 1)[0]


def test_history_does_not_silently_truncate_payg_records_before_filtering():
    payg = log.split("payg_rows = []", 1)[1].split("items: list", 1)[0]
    assert ".limit(limit)" not in payg


def test_historical_data_remains_management_only():
    assert "context.role not in COMPANY_MANAGEMENT_ROLES" in log
    assert "historical_query_enabled" in log
    assert 'CdasHistoricalImportRow.reconciliation_status == "approved"' in log


def test_actual_historical_transaction_date_not_fabricated():
    assert '"historical_date_unverified": True' in log
    assert '"history_timestamp_kind": "imported_at"' in log
    assert 'if (date_from or date_to) and item.get("historical_date_unverified"):' in log
