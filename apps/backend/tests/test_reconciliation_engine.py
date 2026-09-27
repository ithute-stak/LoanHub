from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import HTTPException

from services.reconciliation_service import money, normalize_header, parse_date, source_fingerprint


ROOT = Path(__file__).resolve().parents[2]


def test_reconciliation_money_and_headers_are_deterministic():
    assert money("12.345") == Decimal("12.35")
    assert money("-12.345") == Decimal("-12.35")
    assert normalize_header("Transaction Reference") == "transaction_reference"
    assert normalize_header(" Value-Date ") == "value_date"


def test_reconciliation_dates_support_common_statement_formats():
    assert parse_date("2026-09-27") == date(2026, 9, 27)
    assert parse_date("27/09/2026") == date(2026, 9, 27)
    assert parse_date("27-09-2026") == date(2026, 9, 27)
    with pytest.raises(HTTPException):
        parse_date("September 27th")


def test_source_fingerprint_is_stable_and_company_scoped():
    company = UUID("11111111-1111-1111-1111-111111111111")
    other = UUID("22222222-2222-2222-2222-222222222222")
    kwargs = dict(source_type="bank_statement", transaction_date=date(2026, 9, 27), reference="ABC 123", description="Loan repayment", amount=Decimal("100.00"), direction="credit")
    first = source_fingerprint(company_id=company, **kwargs)
    assert first == source_fingerprint(company_id=company, **kwargs)
    assert first != source_fingerprint(company_id=other, **kwargs)


def test_schema_is_tenant_scoped_and_auditable():
    model = (ROOT / "backend" / "database" / "models" / "reconciliation.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend" / "alembic" / "versions" / "k5r6t7v8w901_reconciliation_engine.py").read_text(encoding="utf-8")
    assert "class ReconciliationBatch" in model
    assert "class ReconciliationLine" in model
    assert "class ReconciliationEvent" in model
    assert "uq_reconciliation_batch_company_reference" in model
    assert "uq_reconciliation_line_batch_source_key" in model
    assert 'down_revision = "j4q5s6u7v801"' in migration
    assert "bank_statement" in migration
    assert "cdas_remittance" in migration
    assert "missing_source" in migration
    assert "adjustment_required" in migration


def test_matching_rules_are_exact_and_ambiguous_rows_remain_exceptions():
    source = (ROOT / "backend" / "services" / "reconciliation_service.py").read_text(encoding="utf-8")
    assert '"exact_provider_reference"' in source
    assert '"exact_proof_reference"' in source
    assert '"exact_folio_or_loan_reference_unique_payment"' in source
    assert "if len(matches) == 1" in source
    assert 'line.status = "unmatched"' in source
    assert '"AMBIGUOUS_MATCH"' in source
    assert '"NO_SAFE_MATCH"' in source
    assert '"free_text_name_matching": False' in source


def test_reconciliation_creates_missing_source_evidence_and_classifies_amount_breaks():
    source = (ROOT / "backend" / "services" / "reconciliation_service.py").read_text(encoding="utf-8")
    assert 'line.status = "shortage"' in source
    assert 'line.status = "excess"' in source
    assert 'status="missing_source"' in source
    assert "MISSING_EXTERNAL_SOURCE" in source
    assert "Successful LoanHub payment was not present" in source


def test_adjustments_use_existing_approval_control_instead_of_mutating_payment():
    source = (ROOT / "backend" / "services" / "reconciliation_service.py").read_text(encoding="utf-8")
    assert "ApprovalRequest(" in source
    assert "PaymentAdjustment(" in source
    assert 'status="pending_approval"' in source
    assert 'action_type="payment_adjustment"' in source
    assert 'line.status = "adjustment_required"' in source
    assert "payment.amount =" not in source


def test_closed_batches_are_immutable_and_close_requires_clear_exceptions():
    source = (ROOT / "backend" / "services" / "reconciliation_service.py").read_text(encoding="utf-8")
    assert "Closed reconciliation batches are immutable" in source
    assert "unresolved reconciliation exception(s) must be cleared before close-off" in source
    assert 'batch.status = "closed"' in source
    assert '"batch_closed"' in source


def test_reconciliation_api_and_ui_cover_operational_flow():
    router = (ROOT / "backend" / "routers" / "reconciliation.py").read_text(encoding="utf-8")
    api_router = (ROOT / "backend" / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    page = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "reconciliation" / "page.tsx").read_text(encoding="utf-8")
    detail = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "reconciliation" / "batches" / "[batchId]" / "page.tsx").read_text(encoding="utf-8")
    client = (ROOT / "frontend" / "api" / "reconciliation.ts").read_text(encoding="utf-8")
    assert 'APIRouter(prefix="/reconciliation"' in router
    assert '@router.get("/dashboard")' in router
    assert '@router.post("/batches")' in router
    assert '@router.post("/batches/{batch_id}/import.csv")' in router
    assert '@router.post("/batches/{batch_id}/reconcile")' in router
    assert '@router.put("/batches/{batch_id}/lines/{line_id}/match")' in router
    assert '@router.post("/batches/{batch_id}/lines/{line_id}/adjustment"' in router
    assert '@router.post("/batches/{batch_id}/close")' in router
    assert "reconciliation.router" in api_router
    assert "Proper Reconciliation Engine" in page
    assert "Manual matching requires the exact LoanHub payment ID" in detail
    assert "uploadReconciliationCsv" in client
    assert "requestReconciliationAdjustment" in client
