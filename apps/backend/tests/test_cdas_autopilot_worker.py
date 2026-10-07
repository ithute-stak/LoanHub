from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_cdas_autopilot_worker_executes_payment_reoptimization_and_window_scan() -> None:
    worker = _read(ROOT / "services/cdas_autopilot_worker.py")

    assert "async def process_pending_payment_reoptimizations(" in worker
    assert "async def scan_affordability_opportunities(" in worker
    assert "async def run_cdas_autopilot_cycle(" in worker
    assert 'plan.get("autopilot_pending")' in worker
    assert 'decision.action == "settle"' in worker
    assert 'decision.action == "shorten_term"' in worker
    assert "await client.check_affordability(" in worker
    assert "affordability_window_open(today)" in worker


def test_autopilot_mutations_use_durable_operation_ledger_and_reconciliation() -> None:
    worker = _read(ROOT / "services/cdas_autopilot_worker.py")

    assert worker.count("execute_provider_operation(") >= 2
    assert worker.count("reconcile_provider_operation(") >= 2
    assert 'operation_type="deduction.modify_active.autopilot"' in worker
    assert 'operation_type="deduction.settle.autopilot"' in worker
    assert 'billing_key=f"cdas-mutation:{operation.id}"' in worker
    assert "state.requires_reconciliation = not reconciled" in worker


def test_cash_settlement_uses_paid_by_employee_reason() -> None:
    worker = _read(ROOT / "services/cdas_autopilot_worker.py")

    assert "settlement_reason=2" in worker
    assert '"reason": "loan_balance_settled"' in worker


def test_topup_requires_explicit_dynamic_consent() -> None:
    worker = _read(ROOT / "services/cdas_autopilot_worker.py")

    assert 'dynamic_top_up_consent=bool(plan.get("dynamic_top_up_consent"))' in worker
    assert '"requires_customer_approval": not decision.execute_automatically' in worker
    assert "if decision.execute_automatically:" in worker


def test_autopilot_clears_payment_work_only_after_provider_confirmation() -> None:
    worker = _read(ROOT / "services/cdas_autopilot_worker.py")

    confirmed_block = worker.split("if confirmed:", 1)[1]
    assert 'plan.pop("autopilot_pending", None)' in confirmed_block
    assert '"autopilot_last_result"' in confirmed_block


def test_autopilot_scheduler_runs_only_through_production_lifespan() -> None:
    main = _read(ROOT / "main.py")
    scheduler = _read(ROOT / "services/cdas_autopilot_scheduler.py")

    assert "start_cdas_autopilot_scheduler" in main
    assert "stop_cdas_autopilot_scheduler" in main
    assert "if not settings.SANDBOX_MODE:" in main
    assert 'name="loanhub-cdas-autopilot"' in scheduler
    assert "timeout=max(300, interval_seconds)" in scheduler
