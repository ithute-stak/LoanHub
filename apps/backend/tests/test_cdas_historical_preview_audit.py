"""Audit safety checks for read-only historical CDAS import previews."""
from pathlib import Path

API = (Path(__file__).resolve().parents[1] / "routers/cdas_api.py").read_text()
PREVIEW = API.split('@router.post("/history/import/preview")', 1)[1].split('@router.get("/history/transactions")', 1)[0]


def test_preview_audit_contains_provenance_and_counts():
    assert "hashlib.sha256(raw).hexdigest()" in PREVIEW
    assert 'action="cdas.historical_import_previewed"' in PREVIEW
    assert '"source_sha256": fingerprint' in PREVIEW
    assert '"reconciliation_counts": reconciliation["counts"]' in PREVIEW
    assert '"persisted": False' in PREVIEW


def test_preview_does_not_mutate_mandates_or_financial_state():
    assert "_require_company_manager(context)" in PREVIEW
    assert "CDASDeductionMandate.company_id == context.company_id" in PREVIEW
    assert "CDASDeductionMandate.branch_id == context.branch_id" in PREVIEW
    assert "db.add(AuditLog(" in PREVIEW
    assert "db.add(CDASDeductionMandate(" not in PREVIEW
    assert "db.add(CDASRemittance" not in PREVIEW
    assert "raw_payload" not in PREVIEW
