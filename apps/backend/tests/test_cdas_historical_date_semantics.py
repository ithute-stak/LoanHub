"""Historical CDAS import timestamps must not be treated as transaction dates."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "routers/cdas_api.py").read_text()
UI = (ROOT.parent / "frontend/app/(dashboard)/company/cdas/history/page.tsx").read_text()
LOG = API.split('@router.get("/history/transactions")', 1)[1].split('@router.get("/history/transactions.pdf")', 1)[0]


def test_date_ranges_exclude_records_without_original_transaction_date():
    assert 'if (date_from or date_to) and item.get("historical_date_unverified"):' in LOG
    assert '"history_timestamp_kind": "imported_at"' in LOG
    assert '"reported_at": None' in LOG
    assert "Import date, not transaction date" in UI


def test_csv_export_preserves_history_provenance():
    EXPORT = API.split('@router.get("/history/transactions.csv")', 1)[1].split('@router.get("/history/deductions")', 1)[0]
    assert '"history_timestamp_kind", "source"' in EXPORT
    assert '"historical_date_unverified"' in EXPORT
