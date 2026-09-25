from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import httpx

from integrations.cdas import CdasError
from services.cdas_operation_ledger import (
    UNRESOLVED_OPERATION_STATES,
    is_ambiguous_write_error,
    operation_fingerprint,
)


ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT / "apps" / "backend" / "database" / "models" / "cdas_official.py"
SERVICE = ROOT / "apps" / "backend" / "services" / "cdas_operation_ledger.py"
ROUTER = ROOT / "apps" / "backend" / "routers" / "cdas_api.py"
MIGRATION = ROOT / "apps" / "backend" / "alembic" / "versions" / "a0o4q6s8t801_cdas_provider_operation_ledger.py"


def test_operation_fingerprint_is_stable_and_scoped() -> None:
    company_id = uuid4()
    request = {
        "EmployeeNo": "EMP-1",
        "DeductionID": 10,
        "DeductionAmount": "500.10",
    }

    first = operation_fingerprint(
        company_id=company_id,
        environment="TEST",
        operation_type="deduction.settle",
        request_snapshot=request,
    )
    reordered = operation_fingerprint(
        company_id=company_id,
        environment="test",
        operation_type="DEDUCTION.SETTLE",
        request_snapshot={
            "DeductionAmount": "500.10",
            "DeductionID": 10,
            "EmployeeNo": "EMP-1",
        },
    )
    different = operation_fingerprint(
        company_id=company_id,
        environment="test",
        operation_type="deduction.modify_active",
        request_snapshot=request,
    )

    assert first == reordered
    assert first != different
    assert len(first) == 64


def _ambiguous_error() -> CdasError:
    try:
        raise httpx.ReadTimeout("provider response timed out")
    except httpx.RequestError as exc:
        try:
            raise CdasError(503, "CDAS service is unavailable") from exc
        except CdasError as error:
            return error


def test_transport_failure_is_ambiguous_but_provider_response_is_not() -> None:
    assert is_ambiguous_write_error(_ambiguous_error()) is True
    assert is_ambiguous_write_error(CdasError(419, "Inactive session")) is False
    assert is_ambiguous_write_error(CdasError(500, "Provider rejected the request")) is False


def test_unresolved_states_block_duplicate_mutations() -> None:
    assert {
        "prepared",
        "submitting",
        "acknowledged",
        "unknown_provider_state",
        "requires_reconciliation",
    } <= UNRESOLVED_OPERATION_STATES

    model_source = MODEL.read_text(encoding="utf-8")
    migration_source = MIGRATION.read_text(encoding="utf-8")

    assert 'class CdasProviderOperation(Base):' in model_source
    assert 'uq_cdas_provider_operation_unresolved_fingerprint' in model_source
    assert "unknown_provider_state" in model_source
    assert "requires_reconciliation" in model_source

    assert 'revision: str = "a0o4q6s8t801"' in migration_source
    assert 'down_revision: Union[str, Sequence[str], None] = "z9n3p5q7r800"' in migration_source
    assert 'uq_cdas_provider_operation_unresolved_fingerprint' in migration_source
    assert "postgresql_where" in migration_source
    assert 'company_branches.id' in migration_source


def test_mutation_routes_use_one_shared_tracked_execution_path() -> None:
    source = ROUTER.read_text(encoding="utf-8")

    assert "execute_provider_operation" in source
    assert source.count("return await _execute_tracked_mutation(") == 3
    assert 'operation_type=f"deduction.lifecycle.{payload.request_type}"' in source
    assert 'operation_type="deduction.modify_active"' in source
    assert 'operation_type="deduction.settle"' in source
    assert 'CDAS_DUPLICATE_UNRESOLVED_OPERATION' in source
    assert '"operation": summary' in source
    assert '"reconciled": reconciled' in source


def test_operation_visibility_and_manual_reconciliation_are_company_scoped() -> None:
    source = ROUTER.read_text(encoding="utf-8")

    assert '@router.get("/operations")' in source
    assert '@router.get("/operations/{operation_id}")' in source
    assert '@router.post("/operations/{operation_id}/reconcile")' in source
    assert 'CdasProviderOperation.company_id == context.company_id' in source
    assert "Read CDAS to reconcile one mutation; this endpoint never replays a write." in source


def test_reconciliation_function_contains_read_calls_only() -> None:
    source = SERVICE.read_text(encoding="utf-8")
    start = source.index("async def reconcile_provider_operation(")
    end = source.index("\ndef operation_summary(", start)
    reconciliation_source = source[start:end]

    assert "view_own_deductions" in reconciliation_source
    assert "get_active_and_approved_deduction" in reconciliation_source
    assert "add_update_deduction" not in reconciliation_source
    assert "modify_active_deduction" not in reconciliation_source
    assert "settle_deduction" not in reconciliation_source
    assert "provider_call" not in reconciliation_source
