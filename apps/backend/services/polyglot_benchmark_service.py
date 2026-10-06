from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from statistics import mean
from time import monotonic
from typing import Callable

from sqlalchemy.orm import Session

from database.models.polyglot_benchmark import PolyglotBenchmarkRun

from services.polyglot_runtime_service import (
    go_digest,
    java_canonicalize_event,
    java_underwriting_rules,
    rust_affordability_assessment,
    rust_loan_preview,
    rust_portfolio_risk_summary,
    rust_predictive_signal_batch,
    rust_variance_classification,
    workload_routing_mode,
)


@dataclass(frozen=True)
class BenchmarkResult:
    workload: str
    worker: str
    iterations: int
    successes: int
    parity_passed: int
    parity_failed: int
    avg_latency_ms: float | None
    max_latency_ms: float | None
    routing_mode: str
    promotion_candidate: bool
    recommendation: str

    def as_dict(self) -> dict:
        return asdict(self)


_THRESHOLDS_MS = {
    "go_reconciliation_hash": 100.0,
    "rust_reconciliation": 100.0,
    "rust_loan_calculation": 250.0,
    "rust_portfolio_risk": 250.0,
    "rust_affordability": 100.0,
    "rust_predictive_risk": 250.0,
    "java_event_processing": 250.0,
    "java_underwriting_rules": 100.0,
}


def _run_case(
    *,
    workload: str,
    worker: str,
    iterations: int,
    operation: Callable[[], tuple[bool, bool]],
) -> BenchmarkResult:
    latencies: list[float] = []
    successes = 0
    parity_passed = 0
    parity_failed = 0

    for _ in range(iterations):
        started = monotonic()
        available, parity = operation()
        elapsed = round((monotonic() - started) * 1000, 3)
        if available:
            successes += 1
            latencies.append(elapsed)
            if parity:
                parity_passed += 1
            else:
                parity_failed += 1

    avg_latency = round(mean(latencies), 3) if latencies else None
    max_latency = round(max(latencies), 3) if latencies else None
    threshold = _THRESHOLDS_MS[workload]
    perfect_parity = successes == iterations and parity_passed == iterations
    within_latency = max_latency is not None and max_latency <= threshold
    candidate = perfect_parity and within_latency

    if successes != iterations:
        recommendation = "keep_shadow_worker_unavailable"
    elif parity_failed:
        recommendation = "keep_shadow_parity_mismatch"
    elif not within_latency:
        recommendation = "keep_shadow_latency_above_threshold"
    else:
        recommendation = "eligible_for_controlled_promotion"

    return BenchmarkResult(
        workload=workload,
        worker=worker,
        iterations=iterations,
        successes=successes,
        parity_passed=parity_passed,
        parity_failed=parity_failed,
        avg_latency_ms=avg_latency,
        max_latency_ms=max_latency,
        routing_mode=workload_routing_mode(workload),
        promotion_candidate=candidate,
        recommendation=recommendation,
    )


def run_polyglot_benchmarks(*, iterations: int = 5) -> dict:
    iterations = max(1, min(int(iterations), 20))

    go_payload = "LoanHub polyglot benchmark"
    go_expected = hashlib.sha256(go_payload.encode("utf-8")).hexdigest()

    def benchmark_go() -> tuple[bool, bool]:
        result = go_digest(correlation_id="benchmark:go-digest", payload=go_payload)
        if result is None:
            return False, False
        return True, str(result.get("sha256") or "").lower() == go_expected

    def benchmark_rust_reconciliation() -> tuple[bool, bool]:
        result = rust_variance_classification(expected_cents=10_000, actual_cents=9_875)
        if result is None:
            return False, False
        return True, (
            result.get("status") == "shortage"
            and int(result.get("variance_cents", 0)) == -125
        )

    expected_schedule = ["363.33", "363.33", "363.34"]

    def benchmark_rust_loan() -> tuple[bool, bool]:
        result = rust_loan_preview(
            method="simple_interest",
            principal="1000.00",
            rate_percent="36.00",
            term_months=3,
            processing_fee="0.00",
            interest_start_date="2026-01-01",
            due_dates=["2026-02-01", "2026-03-01", "2026-04-01"],
        )
        if result is None:
            return False, False
        schedule = [f"{float(item):.2f}" for item in result.get("schedule_amounts", [])]
        return True, (
            f"{float(result.get('monthly_installment')):.2f}" == "363.33"
            and f"{float(result.get('total_interest')):.2f}" == "90.00"
            and f"{float(result.get('total_repayable')):.2f}" == "1090.00"
            and schedule == expected_schedule
        )

    portfolio_rows = [
        {
            "outstanding_balance": "10000.00",
            "principal_amount": "10000.00",
            "days_past_due": 0,
            "active": True,
            "is_written_off": False,
            "is_top_up": False,
            "cdas_collection_enabled": True,
            "first_payment_due": True,
            "first_payment_default": False,
            "origination_month": "2026-01-01",
            "delinquency_bucket": "current",
            "branch_label": "Maseru",
            "product_label": "Standard",
            "employer_label": "Employer A",
        },
        {
            "outstanding_balance": "5000.00",
            "principal_amount": "6000.00",
            "days_past_due": 35,
            "active": True,
            "is_written_off": False,
            "is_top_up": True,
            "cdas_collection_enabled": False,
            "first_payment_due": True,
            "first_payment_default": True,
            "origination_month": "2026-02-01",
            "delinquency_bucket": "31-60",
            "branch_label": "Maseru",
            "product_label": "Standard",
            "employer_label": "Employer B",
        },
        {
            "outstanding_balance": "2000.00",
            "principal_amount": "3000.00",
            "days_past_due": 95,
            "active": False,
            "is_written_off": True,
            "is_top_up": False,
            "cdas_collection_enabled": False,
            "first_payment_due": True,
            "first_payment_default": True,
            "origination_month": "2026-01-01",
            "delinquency_bucket": "90+",
            "branch_label": "Berea",
            "product_label": "Legacy",
            "employer_label": "Employer A",
        },
    ]

    def benchmark_rust_portfolio() -> tuple[bool, bool]:
        result = rust_portfolio_risk_summary(rows=portfolio_rows)
        if result is None:
            return False, False
        try:
            delinquency = {
                str(item["bucket"]): (
                    int(item["loan_count"]),
                    f"{float(item['exposure']):.2f}",
                )
                for item in result.get("delinquency_buckets", [])
            }
            vintages = list(result.get("vintages") or [])
            top_up = list(result.get("top_up_performance") or [])
            parity = (
                f"{float(result.get('active_exposure')):.2f}" == "15000.00"
                and int(result.get("active_loans") or 0) == 2
                and f"{float(result.get('par_30_amount')):.2f}" == "5000.00"
                and f"{float(result.get('par_30')):.2f}" == "33.33"
                and delinquency.get("current") == (1, "10000.00")
                and delinquency.get("31-60") == (1, "5000.00")
                and len(vintages) == 2
                and vintages[0].get("vintage") == "2026-02"
                and f"{float(vintages[0].get('par_30')):.2f}" == "100.00"
                and len(top_up) == 2
                and f"{float(result.get('top_up_exposure')):.2f}" == "5000.00"
                and f"{float(result.get('cdas_exposure')):.2f}" == "10000.00"
                and result.get("authoritative") is False
            )
        except (KeyError, TypeError, ValueError):
            parity = False
        return True, parity

    def benchmark_rust_affordability() -> tuple[bool, bool]:
        result = rust_affordability_assessment(
            base_income="5000.00",
            other_income="500.00",
            living_expenses="1200.00",
            existing_debt_repayments="600.00",
            dependants=2,
            dependant_allowance="250.00",
            living_expense_buffer="300.00",
            proposed_installment="700.00",
            disposable_income_usage_percent="80",
            max_dti_percent="40",
            max_installment_income_percent="35",
            min_verified_net_income="2000.00",
            min_disposable_after_installment="500.00",
        )
        if result is None:
            return False, False
        parity = (
            result.get("passed") is True
            and result.get("monthly_income") == "5500.00"
            and result.get("maximum_affordable_installment") == "1600.00"
            and result.get("affordability_headroom") == "900.00"
            and result.get("disposable_after_installment") == "2200.00"
            and result.get("dti_percent") == "23.636"
            and result.get("authoritative") is False
        )
        return True, parity

    predictive_rows = [
        {
            "key": "loan-1",
            "current_dpd": 12,
            "previous_dpd": 2,
            "current_bucket": "8-30",
            "previous_bucket": "1-7",
            "first_payment_default": True,
            "is_top_up": True,
            "has_work_item": True,
            "work_priority": "high",
            "work_priority_score": "75",
        }
    ]

    def benchmark_rust_predictive() -> tuple[bool, bool]:
        result = rust_predictive_signal_batch(rows=predictive_rows)
        if result is None or len(result) != 1:
            return False, False
        item = result[0]
        return True, (
            item.get("key") == "loan-1"
            and item.get("risk_score") == "74"
            and item.get("risk_band") == "high"
            and item.get("projected_par30_entry") is True
            and item.get("stress_bucket_30d") == "31-60"
            and item.get("authoritative") is None
        )

    def benchmark_java_underwriting() -> tuple[bool, bool]:
        result = java_underwriting_rules(
            monthly_income="5500.00",
            min_verified_net_income="2000.00",
            proposed_installment="700.00",
            maximum_affordable_installment="1600.00",
            disposable_after_installment="2200.00",
            min_disposable_after_installment="500.00",
        )
        if result is None:
            return False, False
        reasons = result.get("reasons") or []
        codes = [item.get("code") for item in reasons if isinstance(item, dict)]
        return True, (
            result.get("passed") is True
            and result.get("decision") == "pass"
            and codes == ["income_ok", "installment_within_limit"]
        )

    java_payload = {"z": 1, "a": {"y": 2, "b": 3}}
    java_expected = json.dumps(java_payload, sort_keys=True, separators=(",", ":"))
    java_hash = hashlib.sha256(java_expected.encode("utf-8")).hexdigest()

    def benchmark_java() -> tuple[bool, bool]:
        result = java_canonicalize_event(
            correlation_id="benchmark:java-event",
            event_type="benchmark.runtime",
            payload=java_payload,
        )
        if result is None:
            return False, False
        return True, (
            result.get("canonical_json") == java_expected
            and result.get("payload_sha256") == java_hash
        )

    results = [
        _run_case(
            workload="go_reconciliation_hash",
            worker="go_worker",
            iterations=iterations,
            operation=benchmark_go,
        ),
        _run_case(
            workload="rust_reconciliation",
            worker="rust_compute",
            iterations=iterations,
            operation=benchmark_rust_reconciliation,
        ),
        _run_case(
            workload="rust_loan_calculation",
            worker="rust_compute",
            iterations=iterations,
            operation=benchmark_rust_loan,
        ),
        _run_case(
            workload="rust_portfolio_risk",
            worker="rust_compute",
            iterations=iterations,
            operation=benchmark_rust_portfolio,
        ),
        _run_case(
            workload="rust_affordability",
            worker="rust_compute",
            iterations=iterations,
            operation=benchmark_rust_affordability,
        ),
        _run_case(
            workload="rust_predictive_risk",
            worker="rust_compute",
            iterations=iterations,
            operation=benchmark_rust_predictive,
        ),
        _run_case(
            workload="java_underwriting_rules",
            worker="java_worker",
            iterations=iterations,
            operation=benchmark_java_underwriting,
        ),
        _run_case(
            workload="java_event_processing",
            worker="java_worker",
            iterations=iterations,
            operation=benchmark_java,
        ),
    ]

    return {
        "iterations": iterations,
        "non_authoritative": True,
        "changes_routing": False,
        "criteria": {
            workload: {
                "required_parity_rate": 1.0,
                "max_latency_ms": threshold,
                "required_success_rate": 1.0,
            }
            for workload, threshold in _THRESHOLDS_MS.items()
        },
        "results": [result.as_dict() for result in results],
    }



def persist_benchmark_run(
    db: Session,
    *,
    requested_by_user_id,
    benchmark: dict,
    routing: dict,
) -> PolyglotBenchmarkRun:
    results = list(benchmark.get("results") or [])
    candidates = sum(1 for item in results if item.get("promotion_candidate") is True)
    total = len(results)
    all_candidates = total > 0 and candidates == total
    summary = (
        f"{candidates}/{total} workloads eligible for controlled promotion"
        if total
        else "No benchmark workloads completed"
    )

    record = PolyglotBenchmarkRun(
        requested_by_user_id=requested_by_user_id,
        iterations=int(benchmark.get("iterations") or 0),
        all_candidates=all_candidates,
        promotion_candidate_count=candidates,
        summary=summary,
        criteria=dict(benchmark.get("criteria") or {}),
        results=results,
        routing_snapshot=dict(routing or {}),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_benchmark_history(db: Session, *, limit: int = 20) -> list[dict]:
    rows = (
        db.query(PolyglotBenchmarkRun)
        .order_by(PolyglotBenchmarkRun.created_at.desc())
        .limit(max(1, min(int(limit), 100)))
        .all()
    )
    return [
        {
            "id": str(row.id),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "requested_by_user_id": (
                str(row.requested_by_user_id) if row.requested_by_user_id else None
            ),
            "iterations": row.iterations,
            "all_candidates": row.all_candidates,
            "promotion_candidate_count": row.promotion_candidate_count,
            "summary": row.summary,
            "criteria": row.criteria,
            "results": row.results,
            "routing_snapshot": row.routing_snapshot,
        }
        for row in rows
    ]
