from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from statistics import mean
from time import monotonic
from typing import Callable

from services.polyglot_runtime_service import (
    go_digest,
    java_canonicalize_event,
    rust_loan_preview,
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
    "java_event_processing": 250.0,
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
