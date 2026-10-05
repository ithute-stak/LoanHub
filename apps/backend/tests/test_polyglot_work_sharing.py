from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def test_polyglot_runtime_boundaries_are_present() -> None:
    architecture = (REPO / "docs/POLYGLOT_WORK_SHARING.md").read_text(encoding="utf-8")
    runtime = (ROOT / "services/polyglot_runtime_service.py").read_text(encoding="utf-8")

    assert "Python/FastAPI remains the business authority" in architecture
    assert "Rust/WASM" in architecture
    assert "Go" in architecture
    assert "C++" in architecture
    assert "LOANHUB_RUST_COMPUTE_URL" in runtime
    assert "LOANHUB_GO_WORKER_URL" in runtime
    assert "non-authoritative acceleration" in runtime
    assert "returns None so callers keep using Python" in runtime


def test_workers_are_bounded_and_health_checked() -> None:
    rust = (REPO / "services/compute-rust/src/main.rs").read_text(encoding="utf-8")
    go = (REPO / "services/worker-go/main.go").read_text(encoding="utf-8")
    native = (REPO / "services/native-cpp/src/main.cpp").read_text(encoding="utf-8")
    wasm = (REPO / "apps/frontend/wasm/loanhub-compute/src/lib.rs").read_text(encoding="utf-8")

    assert "/health/ready" in rust
    assert '"authoritative": false' in rust or '"authoritative":false' in rust
    assert "/health/ready" in go
    assert "/v1/digest" in go
    assert "simple-interest" in native
    assert "round_ratio_half_up" in native
    assert "Server-side Python remains authoritative" in wasm


def test_go_hashing_has_python_fallback(monkeypatch) -> None:
    from services import polyglot_runtime_service as runtime

    monkeypatch.setenv("LOANHUB_GO_WORKER_URL", "http://go-worker:8081")
    monkeypatch.setattr(runtime, "_post_json", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("down")))

    value = runtime.stable_sha256_text(correlation_id="test", payload="LoanHub")
    assert value == "e400d25405baf415cc81bf1dfe8dea967d55a09c4e8e862e5a9c98fcd6f033c6"


def test_go_hashing_accepts_valid_worker_digest(monkeypatch) -> None:
    from services import polyglot_runtime_service as runtime

    import hashlib

    digest = hashlib.sha256(b"anything").hexdigest()
    monkeypatch.setenv("LOANHUB_GO_WORKER_URL", "http://go-worker:8081")
    monkeypatch.setenv("LOANHUB_GO_RECON_HASH_MODE", "prefer-worker")
    monkeypatch.setattr(runtime, "_post_json", lambda *args, **kwargs: {"sha256": digest})

    assert runtime.stable_sha256_text(correlation_id="test", payload="anything") == digest


def test_rust_variance_classification_validates_worker_response(monkeypatch) -> None:
    from services import polyglot_runtime_service as runtime

    monkeypatch.setenv("LOANHUB_RUST_COMPUTE_URL", "http://rust-compute:8082")
    monkeypatch.setattr(
        runtime,
        "_get_json",
        lambda *args, **kwargs: {
            "status": "shortage",
            "variance_cents": -125,
            "authoritative": False,
        },
    )

    assert runtime.rust_variance_classification(
        expected_cents=1000,
        actual_cents=875,
    ) == {
        "status": "shortage",
        "variance_cents": -125,
        "authoritative": False,
    }


def test_reconciliation_uses_go_and_rust_with_python_safety() -> None:
    service = (ROOT / "services/reconciliation_service.py").read_text(encoding="utf-8")

    assert "stable_sha256_text(" in service
    assert "rust_variance_classification(" in service
    assert 'workload_routing_mode("rust_reconciliation")' in service
    assert 'routing_mode == "prefer-worker"' in service
    assert '"matched" if variance == 0 else "shortage" if variance < 0 else "excess"' in service


def test_rust_loan_preview_is_used_only_after_python_parity(monkeypatch) -> None:
    from datetime import date
    from decimal import Decimal

    from database.models.enums import LoanCalculationMethod
    from services import interest_calculation_service as interest

    monkeypatch.setenv("LOANHUB_RUST_LOAN_CALC_MODE", "prefer-worker")
    monkeypatch.setattr(
        interest,
        "rust_loan_preview",
        lambda **kwargs: {
            "method": "simple_interest",
            "monthly_installment": "363.33",
            "total_interest": "90.00",
            "total_repayable": "1090.00",
            "schedule_amounts": ["363.33", "363.33", "363.34"],
            "authoritative": False,
        },
    )

    monthly, total, details = interest.calculate_loan_terms(
        principal=Decimal("1000"),
        rate_percent=Decimal("36"),
        term_months=3,
        processing_fee=Decimal("0"),
        interest_method=LoanCalculationMethod.SIMPLE_INTEREST,
        start_date=date(2026, 1, 1),
        due_dates=[date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)],
    )

    assert monthly == Decimal("363.33")
    assert total == Decimal("1090.00")
    assert details["compute_runtime"] == {
        "python_authoritative": True,
        "rust_used": True,
        "rust_shadow": False,
        "rust_parity": "passed",
        "rust_routing_mode": "prefer-worker",
        "cpp_used": False,
        "fallback": False,
    }


def test_rust_loan_preview_mismatch_falls_back_to_python(monkeypatch) -> None:
    from datetime import date
    from decimal import Decimal

    from database.models.enums import LoanCalculationMethod
    from services import interest_calculation_service as interest

    monkeypatch.setenv("LOANHUB_RUST_LOAN_CALC_MODE", "prefer-worker")
    monkeypatch.setattr(
        interest,
        "rust_loan_preview",
        lambda **kwargs: {
            "method": "simple_interest",
            "monthly_installment": "999.99",
            "total_interest": "999.99",
            "total_repayable": "999.99",
            "schedule_amounts": ["999.99", "999.99", "999.99"],
            "authoritative": False,
        },
    )

    monthly, total, details = interest.calculate_loan_terms(
        principal=Decimal("1000"),
        rate_percent=Decimal("36"),
        term_months=3,
        processing_fee=Decimal("0"),
        interest_method=LoanCalculationMethod.SIMPLE_INTEREST,
        start_date=date(2026, 1, 1),
        due_dates=[date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)],
    )

    assert monthly == Decimal("363.33")
    assert total == Decimal("1090.00")
    assert details["compute_runtime"]["python_authoritative"] is True
    assert details["compute_runtime"]["rust_used"] is False
    assert details["compute_runtime"]["rust_parity"] == "mismatch"
    assert details["compute_runtime"]["fallback"] is True


def test_rust_loan_engine_supports_first_deterministic_methods() -> None:
    rust = (REPO / "services/compute-rust/src/main.rs").read_text(encoding="utf-8")
    service = (ROOT / "services/interest_calculation_service.py").read_text(encoding="utf-8")

    assert '"/v1/loan-preview"' in rust
    assert '"micro_loan" => micro_loan(req)' in rust
    assert '"simple_interest" | "flat_rate" => simple_or_flat(req)' in rust
    assert '"compound_interest" => compound(req)' in rust
    assert '"reducing_balance" => reducing_balance(req)' in rust
    assert '"daily_accrual_reducing" => daily_accrual_reducing(req)' in rust
    assert "fn daily_segment_interest(" in rust
    assert "fn daily_period_factor(" in rust
    rust_supported = service.split("rust_supported =", 1)[1].split("}", 1)[0]
    assert "LoanCalculationMethod.REDUCING_BALANCE" in rust_supported
    assert "LoanCalculationMethod.DAILY_ACCRUAL_REDUCING" in rust_supported


def test_java_event_worker_is_registered_and_non_authoritative() -> None:
    runtime = (ROOT / "services/polyglot_runtime_service.py").read_text(encoding="utf-8")
    java = (REPO / "services/worker-java/src/main/java/ls/co/loanhub/worker/EventWorker.java").read_text(encoding="utf-8")
    compose = (REPO / "compose.yaml").read_text(encoding="utf-8")

    assert "LOANHUB_JAVA_WORKER_URL" in runtime
    assert "def java_canonicalize_event(" in runtime
    assert "def java_event_batch_summary(" in runtime
    assert '"/v1/events/canonicalize"' in java
    assert '"/v1/events/batch-summary"' in java
    assert '"authoritative", false' in java
    assert "java-worker:" in compose
    assert "worker-java.jar" in compose


def test_webhook_event_canonicalization_uses_java_only_after_payload_parity(monkeypatch) -> None:
    import hashlib
    from types import SimpleNamespace

    from services import webhook_outbox_service as webhook

    event = SimpleNamespace(
        id="event-1",
        event_type="loan.approved",
        payload={"z": 1, "a": {"y": 2, "b": 3}},
    )
    canonical = '{"a":{"b":3,"y":2},"z":1}'
    monkeypatch.setattr(
        webhook,
        "java_canonicalize_event",
        lambda **kwargs: {
            "authoritative": False,
            "correlation_id": "webhook:event-1",
            "event_type": "loan.approved",
            "canonical_json": canonical,
            "payload_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        },
    )

    assert webhook._canonical_event_body(event) == canonical.encode()


def test_webhook_event_canonicalization_falls_back_on_java_mismatch(monkeypatch) -> None:
    from types import SimpleNamespace

    from services import webhook_outbox_service as webhook

    event = SimpleNamespace(
        id="event-2",
        event_type="payment.received",
        payload={"amount": 100, "currency": "LSL"},
    )
    monkeypatch.setattr(
        webhook,
        "java_canonicalize_event",
        lambda **kwargs: {
            "authoritative": False,
            "correlation_id": "webhook:event-2",
            "event_type": "payment.received",
            "canonical_json": '{"amount":999,"currency":"LSL"}',
            "payload_sha256": "0" * 64,
        },
    )

    assert webhook._canonical_event_body(event) == b'{"amount":100,"currency":"LSL"}'


def test_cpp_kernel_is_bundled_behind_rust_compute() -> None:
    native = (REPO / "services/native-cpp/src/main.cpp").read_text(encoding="utf-8")
    rust = (REPO / "services/compute-rust/src/main.rs").read_text(encoding="utf-8")
    dockerfile = (REPO / "services/compute-rust/Dockerfile").read_text(encoding="utf-8")

    assert "simple-interest" in native
    assert "round_ratio_half_up" in native
    assert "LOANHUB_CPP_KERNEL_PATH" in rust
    assert "cpp_simple_interest_cents(" in rust
    assert "native_cpp_used" in rust
    assert "COPY --from=cpp-build" in dockerfile
    assert "loanhub-native" in dockerfile


def test_rust_wasm_browser_preview_is_built_and_parity_checked() -> None:
    wasm = (REPO / "apps/frontend/wasm/loanhub-compute/src/lib.rs").read_text(encoding="utf-8")
    loader = (REPO / "apps/frontend/lib/wasm-loan-compute.ts").read_text(encoding="utf-8")
    api = (REPO / "apps/frontend/api/loans.ts").read_text(encoding="utf-8")
    dockerfile = (REPO / "apps/frontend/Dockerfile").read_text(encoding="utf-8")

    assert "simple_interest_total_cents" in wasm
    assert "affordability_headroom_cents" in wasm
    assert 'fetch("/wasm/loanhub_compute_wasm.wasm"' in loader
    assert "simpleInterestBrowserPreview" in api
    assert "wasm_parity" in api
    assert 'Math.abs(previewTotal - Number(result.total_repayable)) < 0.005' in api
    assert "wasm32-unknown-unknown" in dockerfile
    assert "loanhub_compute_wasm.wasm" in dockerfile


def test_polyglot_circuit_breaker_opens_after_repeated_failures(monkeypatch) -> None:
    from services import polyglot_runtime_service as runtime

    runtime._runtime_state.clear()
    monkeypatch.setenv("LOANHUB_GO_WORKER_URL", "http://go-worker:8081")
    monkeypatch.setattr(
        runtime,
        "_post_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("down")),
    )

    for _ in range(runtime._CIRCUIT_FAILURE_THRESHOLD):
        assert runtime.go_digest(correlation_id="test", payload="LoanHub") is None

    metrics = runtime.runtime_metrics()["go_worker"]
    assert metrics["circuit_open"] is True
    assert metrics["consecutive_failures"] == runtime._CIRCUIT_FAILURE_THRESHOLD
    assert metrics["fallbacks"] >= runtime._CIRCUIT_FAILURE_THRESHOLD


def test_runtime_status_exposes_worker_metrics_and_circuit_breakers() -> None:
    service = (ROOT / "services/polyglot_runtime_service.py").read_text(encoding="utf-8")
    router = (ROOT / "routers/polyglot_runtime.py").read_text(encoding="utf-8")

    assert "_CIRCUIT_FAILURE_THRESHOLD = 3" in service
    assert "_CIRCUIT_OPEN_SECONDS = 30.0" in service
    assert "def runtime_metrics(" in service
    assert '"circuit_open"' in service
    assert '"parity_mismatches"' in service
    assert '"runtime_metrics": runtime_metrics()' in router


def test_workload_routing_defaults_and_overrides(monkeypatch) -> None:
    from services import polyglot_runtime_service as runtime

    monkeypatch.delenv("LOANHUB_RUST_LOAN_CALC_MODE", raising=False)
    assert runtime.workload_routing_mode("rust_loan_calculation") == "shadow"

    monkeypatch.setenv("LOANHUB_RUST_LOAN_CALC_MODE", "prefer-worker")
    assert runtime.workload_routing_mode("rust_loan_calculation") == "prefer-worker"

    monkeypatch.setenv("LOANHUB_RUST_LOAN_CALC_MODE", "invalid")
    assert runtime.workload_routing_mode("rust_loan_calculation") == "shadow"


def test_go_hash_mismatch_falls_back_to_python_and_records_parity(monkeypatch) -> None:
    import hashlib

    from services import polyglot_runtime_service as runtime

    runtime._runtime_state.clear()
    monkeypatch.setenv("LOANHUB_GO_WORKER_URL", "http://go-worker:8081")
    monkeypatch.setenv("LOANHUB_GO_RECON_HASH_MODE", "prefer-worker")
    monkeypatch.setattr(runtime, "_post_json", lambda *args, **kwargs: {"sha256": "a" * 64})

    expected = hashlib.sha256(b"anything").hexdigest()
    assert runtime.stable_sha256_text(correlation_id="test", payload="anything") == expected
    assert runtime.runtime_metrics()["go_worker"]["parity_mismatches"] == 1


def test_daily_accrual_rust_shadow_receives_exact_dates_and_keeps_python_authority(monkeypatch) -> None:
    from datetime import date
    from decimal import Decimal

    from database.models.enums import LoanCalculationMethod
    from services import interest_calculation_service as interest

    captured: dict[str, object] = {}

    def fake_preview(**kwargs):
        captured.update(kwargs)
        return {
            "method": "daily_accrual_reducing",
            "monthly_installment": "999.99",
            "total_interest": "999.99",
            "total_repayable": "999.99",
            "schedule_amounts": ["999.99", "999.99", "999.99"],
            "authoritative": False,
            "native_cpp_used": False,
        }

    monkeypatch.setenv("LOANHUB_RUST_LOAN_CALC_MODE", "shadow")
    monkeypatch.setattr(interest, "rust_loan_preview", fake_preview)

    monthly, total, details = interest.calculate_loan_terms(
        principal=Decimal("1000"),
        rate_percent=Decimal("36"),
        term_months=3,
        processing_fee=Decimal("0"),
        interest_method=LoanCalculationMethod.DAILY_ACCRUAL_REDUCING,
        start_date=date(2024, 4, 24),
        due_dates=[date(2024, 5, 24), date(2024, 6, 24), date(2024, 7, 24)],
    )

    assert captured["interest_start_date"] == "2024-04-24"
    assert captured["due_dates"] == ["2024-05-24", "2024-06-24", "2024-07-24"]
    assert monthly == Decimal(details["monthly_installment"])
    assert total == Decimal(details["total_repayable"])
    assert details["compute_runtime"]["rust_used"] is False
    assert details["compute_runtime"]["rust_routing_mode"] == "shadow"
    assert details["compute_runtime"]["rust_parity"] == "mismatch"
    assert details["compute_runtime"]["fallback"] is True


def test_polyglot_benchmark_reports_only_full_parity_candidates(monkeypatch) -> None:
    import hashlib
    import json

    from services import polyglot_benchmark_service as benchmark

    monkeypatch.setattr(
        benchmark,
        "go_digest",
        lambda **kwargs: {
            "sha256": hashlib.sha256(kwargs["payload"].encode("utf-8")).hexdigest()
        },
    )
    monkeypatch.setattr(
        benchmark,
        "rust_variance_classification",
        lambda **kwargs: {"status": "shortage", "variance_cents": -125},
    )
    monkeypatch.setattr(
        benchmark,
        "rust_loan_preview",
        lambda **kwargs: {
            "monthly_installment": "363.33",
            "total_interest": "90.00",
            "total_repayable": "1090.00",
            "schedule_amounts": ["363.33", "363.33", "363.34"],
        },
    )
    monkeypatch.setattr(
        benchmark,
        "rust_affordability_assessment",
        lambda **kwargs: {
            "passed": True,
            "monthly_income": "5500.00",
            "maximum_affordable_installment": "1600.00",
            "affordability_headroom": "900.00",
            "disposable_after_installment": "2200.00",
            "dti_percent": "23.636",
            "authoritative": False,
        },
    )
    monkeypatch.setattr(
        benchmark,
        "rust_predictive_signal_batch",
        lambda **kwargs: [
            {
                "key": "loan-1",
                "risk_score": "74",
                "risk_band": "high",
                "projected_par30_entry": True,
                "stress_bucket_30d": "31-60",
                "rationale": [],
                "recommended_action": "Review",
            }
        ],
    )
    monkeypatch.setattr(
        benchmark,
        "java_underwriting_rules",
        lambda **kwargs: {
            "passed": True,
            "decision": "pass",
            "reasons": [
                {"severity": "pass", "code": "income_ok", "message": "Monthly income meets the lender's configured minimum."},
                {"severity": "pass", "code": "installment_within_limit", "message": "The proposed installment is within the calculated affordability limit."},
            ],
            "authoritative": False,
        },
    )
    monkeypatch.setattr(
        benchmark,
        "rust_portfolio_risk_summary",
        lambda **kwargs: {
            "active_exposure": "15000.00",
            "active_loans": 2,
            "par_30_amount": "5000.00",
            "par_30": "33.33",
            "delinquency_buckets": [
                {"bucket": "current", "loan_count": 1, "exposure": "10000.00"},
                {"bucket": "1-7", "loan_count": 0, "exposure": "0.00"},
                {"bucket": "8-30", "loan_count": 0, "exposure": "0.00"},
                {"bucket": "31-60", "loan_count": 1, "exposure": "5000.00"},
                {"bucket": "61-90", "loan_count": 0, "exposure": "0.00"},
                {"bucket": "90+", "loan_count": 0, "exposure": "0.00"},
            ],
            "vintages": [
                {"vintage": "2026-02", "par_30": "100.00"},
                {"vintage": "2026-01", "par_30": "0.00"},
            ],
            "top_up_performance": [
                {"label": "New / non-top-up"},
                {"label": "Top-up"},
            ],
            "top_up_exposure": "5000.00",
            "cdas_exposure": "10000.00",
            "authoritative": False,
        },
    )
    java_payload = {"z": 1, "a": {"y": 2, "b": 3}}
    canonical = json.dumps(java_payload, sort_keys=True, separators=(",", ":"))
    monkeypatch.setattr(
        benchmark,
        "java_canonicalize_event",
        lambda **kwargs: {
            "canonical_json": canonical,
            "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        },
    )
    monkeypatch.setattr(benchmark, "workload_routing_mode", lambda workload: "shadow")

    result = benchmark.run_polyglot_benchmarks(iterations=2)

    assert result["iterations"] == 2
    assert result["non_authoritative"] is True
    assert result["changes_routing"] is False
    assert len(result["results"]) == 8
    assert all(item["parity_passed"] == 2 for item in result["results"])
    assert all(item["promotion_candidate"] is True for item in result["results"])


def test_polyglot_benchmark_caps_iterations(monkeypatch) -> None:
    from services import polyglot_benchmark_service as benchmark

    monkeypatch.setattr(
        benchmark,
        "_run_case",
        lambda **kwargs: benchmark.BenchmarkResult(
            workload=kwargs["workload"],
            worker=kwargs["worker"],
            iterations=kwargs["iterations"],
            successes=0,
            parity_passed=0,
            parity_failed=0,
            avg_latency_ms=None,
            max_latency_ms=None,
            routing_mode="shadow",
            promotion_candidate=False,
            recommendation="keep_shadow_worker_unavailable",
        ),
    )

    result = benchmark.run_polyglot_benchmarks(iterations=999)
    assert result["iterations"] == 20
    assert all(item["iterations"] == 20 for item in result["results"])


def test_rust_portfolio_risk_batch_kernel_is_shadow_routed() -> None:
    rust = (REPO / "services/compute-rust/src/main.rs").read_text(encoding="utf-8")
    runtime = (ROOT / "services/polyglot_runtime_service.py").read_text(encoding="utf-8")
    portfolio = (ROOT / "services/portfolio_risk_service.py").read_text(encoding="utf-8")
    env = (REPO / ".env.example").read_text(encoding="utf-8")

    assert '"/v1/portfolio-risk-summary"' in rust
    assert "struct PortfolioRiskRequest" in rust
    assert "fn portfolio_risk_summary(" in rust
    assert '"rust_portfolio_risk": "shadow"' in runtime
    assert "def rust_portfolio_risk_summary(" in runtime
    assert 'workload_routing_mode("rust_portfolio_risk")' in portfolio
    assert 'record_parity_mismatch("rust_compute")' in portfolio
    assert "LOANHUB_RUST_PORTFOLIO_RISK_MODE=shadow" in env


def test_portfolio_risk_keeps_activity_policy_in_python() -> None:
    portfolio = (ROOT / "services/portfolio_risk_service.py").read_text(encoding="utf-8")
    rust = (REPO / "services/compute-rust/src/main.rs").read_text(encoding="utf-8")

    assert '"active": (' in portfolio
    assert "row.loan_status in active_names" in portfolio
    assert "money(row.outstanding_balance) > 0" in portfolio
    assert "not row.is_written_off" in portfolio
    assert "row.active" in rust


def test_go_webhook_delivery_is_bounded_and_python_authoritative() -> None:
    go = (REPO / "services/worker-go/main.go").read_text(encoding="utf-8")
    runtime = (ROOT / "services/polyglot_runtime_service.py").read_text(encoding="utf-8")
    webhook = (ROOT / "services/webhook_outbox_service.py").read_text(encoding="utf-8")
    env = (REPO / ".env.example").read_text(encoding="utf-8")

    assert '"/v1/webhooks/deliver-batch"' in go
    assert "sync.WaitGroup" in go
    assert "webhookConcurrency()" in go
    assert "blockedIP(" in go
    assert "http.ErrUseLastResponse" in go
    assert '"go_webhook_delivery": "off"' in runtime
    assert "def go_webhook_delivery_batch(" in runtime
    assert 'workload_routing_mode("go_webhook_delivery") == "prefer-worker"' in webhook
    assert "Shadow is deliberately Python-only" in webhook
    assert "LOANHUB_GO_WEBHOOK_DELIVERY_MODE=off" in env


def test_go_webhook_batch_success_updates_python_owned_state(monkeypatch) -> None:
    from types import SimpleNamespace
    from uuid import uuid4

    from services import webhook_outbox_service as webhook

    event = SimpleNamespace(
        id=uuid4(),
        endpoint_id=uuid4(),
        event_type="loan.approved",
        payload={"loan_id": "123"},
        attempt_count=0,
        last_attempt_at=None,
        status="pending",
        delivered_at=None,
        last_error=None,
        next_attempt_at=None,
        response_status=None,
    )
    endpoint = SimpleNamespace(
        failure_count=2,
        last_delivery_at=None,
    )

    class FakeDB:
        def __init__(self):
            self.added = []

        def get(self, model, key):
            return endpoint

        def add(self, value):
            self.added.append(value)

    db = FakeDB()
    monkeypatch.setattr(
        webhook,
        "_prepare_go_delivery_job",
        lambda db, event: (
            endpoint,
            {
                "job_id": str(event.id),
                "url": "https://example.com/webhook",
                "headers": {},
                "body": "{}",
                "timeout_ms": 1000,
            },
        ),
    )
    monkeypatch.setattr(
        webhook,
        "go_webhook_delivery_batch",
        lambda **kwargs: [
            {
                "job_id": str(event.id),
                "status_code": 204,
                "response_body_sha256": "a" * 64,
                "duration_ms": 12,
            }
        ],
    )

    webhook._deliver_batch_via_go(db, [event])

    assert event.attempt_count == 1
    assert event.status == "delivered"
    assert event.response_status == 204
    assert event.last_error is None
    assert endpoint.failure_count == 0
    assert endpoint.last_delivery_at is not None
    assert db.added


def test_go_webhook_ambiguous_worker_failure_does_not_immediately_python_replay(monkeypatch) -> None:
    from types import SimpleNamespace
    from uuid import uuid4

    from services import webhook_outbox_service as webhook

    event = SimpleNamespace(
        id=uuid4(),
        endpoint_id=uuid4(),
        event_type="payment.received",
        payload={"payment_id": "123"},
        attempt_count=0,
        last_attempt_at=None,
        status="pending",
        delivered_at=None,
        last_error=None,
        next_attempt_at=None,
        response_status=None,
    )
    endpoint = SimpleNamespace(
        failure_count=0,
        last_delivery_at=None,
    )

    class FakeDB:
        def __init__(self):
            self.added = []

        def get(self, model, key):
            return endpoint

        def add(self, value):
            self.added.append(value)

    db = FakeDB()
    python_replay_calls = {"count": 0}

    def forbidden_python_replay(*args, **kwargs):
        python_replay_calls["count"] += 1
        raise AssertionError("must not immediately replay an ambiguous Go delivery")

    monkeypatch.setattr(webhook, "_deliver", forbidden_python_replay)
    monkeypatch.setattr(
        webhook,
        "_prepare_go_delivery_job",
        lambda db, event: (
            endpoint,
            {
                "job_id": str(event.id),
                "url": "https://example.com/webhook",
                "headers": {},
                "body": "{}",
                "timeout_ms": 1000,
            },
        ),
    )
    monkeypatch.setattr(webhook, "go_webhook_delivery_batch", lambda **kwargs: None)

    webhook._deliver_batch_via_go(db, [event])

    assert python_replay_calls["count"] == 0
    assert event.attempt_count == 1
    assert event.status in {"retrying", "dead_letter"}
    assert "outcome unknown" in event.last_error
    assert endpoint.failure_count == 1


def test_rust_portfolio_risk_phase_two_moves_more_snapshot_loops() -> None:
    rust = (REPO / "services/compute-rust/src/main.rs").read_text(encoding="utf-8")
    portfolio = (ROOT / "services/portfolio_risk_service.py").read_text(encoding="utf-8")
    benchmark = (ROOT / "services/polyglot_benchmark_service.py").read_text(encoding="utf-8")

    assert "fn delinquency_buckets(" in rust
    assert "fn vintage_summaries(" in rust
    assert "fn top_up_performance(" in rust
    assert "top_up_exposure:" in rust
    assert "cdas_exposure:" in rust
    assert "def _python_risk_aggregation(" in portfolio
    assert '"promoted_no_live_parity"' in portfolio
    assert 'workload="rust_portfolio_risk"' in benchmark
    assert '"rust_portfolio_risk": 250.0' in benchmark


def test_rust_portfolio_risk_normalizer_matches_python_contract() -> None:
    from datetime import date
    from types import SimpleNamespace

    from database.models.enums import LoanStatus
    from services import portfolio_risk_service as portfolio

    rows = [
        SimpleNamespace(
            outstanding_balance="10000.00",
            principal_amount="10000.00",
            days_past_due=0,
            loan_status=LoanStatus.ACTIVE.value,
            is_written_off=False,
            is_top_up=False,
            cdas_collection_enabled=True,
            evidence_snapshot={"first_payment_due": True},
            first_payment_default=False,
            origination_month=date(2026, 1, 1),
            delinquency_bucket="current",
            branch_label="Maseru",
            product_label="Standard",
            employer_label="Employer A",
        ),
        SimpleNamespace(
            outstanding_balance="5000.00",
            principal_amount="6000.00",
            days_past_due=35,
            loan_status=LoanStatus.ACTIVE.value,
            is_written_off=False,
            is_top_up=True,
            cdas_collection_enabled=False,
            evidence_snapshot={"first_payment_due": True},
            first_payment_default=True,
            origination_month=date(2026, 2, 1),
            delinquency_bucket="31-60",
            branch_label="Maseru",
            product_label="Standard",
            employer_label="Employer B",
        ),
    ]

    python_value = portfolio._python_risk_aggregation(rows)
    rust_value = {
        "active_exposure": "15000.00",
        "active_loans": 2,
        "par_1_amount": "5000.00",
        "par_1": "33.33",
        "par_7_amount": "5000.00",
        "par_7": "33.33",
        "par_30_amount": "5000.00",
        "par_30": "33.33",
        "par_60_amount": "0.00",
        "par_60": "0.00",
        "par_90_amount": "0.00",
        "par_90": "0.00",
        "branch": {
            "hhi": "10000.00",
            "top_share_percent": "100.00",
            "group_count": 1,
            "groups": [{
                "label": "Maseru",
                "loan_count": 2,
                "exposure": "15000.00",
                "share_percent": "100.00",
                "par_30": "33.33",
                "fpd_rate": "50.00",
            }],
        },
        "product": {
            "hhi": "10000.00",
            "top_share_percent": "100.00",
            "group_count": 1,
            "groups": [{
                "label": "Standard",
                "loan_count": 2,
                "exposure": "15000.00",
                "share_percent": "100.00",
                "par_30": "33.33",
                "fpd_rate": "50.00",
            }],
        },
        "employer": {
            "hhi": "5555.78",
            "top_share_percent": "66.67",
            "group_count": 2,
            "groups": [
                {
                    "label": "Employer A",
                    "loan_count": 1,
                    "exposure": "10000.00",
                    "share_percent": "66.67",
                    "par_30": "0.00",
                    "fpd_rate": "0.00",
                },
                {
                    "label": "Employer B",
                    "loan_count": 1,
                    "exposure": "5000.00",
                    "share_percent": "33.33",
                    "par_30": "100.00",
                    "fpd_rate": "100.00",
                },
            ],
        },
        "delinquency_buckets": [
            {"bucket": "current", "loan_count": 1, "exposure": "10000.00"},
            {"bucket": "1-7", "loan_count": 0, "exposure": "0.00"},
            {"bucket": "8-30", "loan_count": 0, "exposure": "0.00"},
            {"bucket": "31-60", "loan_count": 1, "exposure": "5000.00"},
            {"bucket": "61-90", "loan_count": 0, "exposure": "0.00"},
            {"bucket": "90+", "loan_count": 0, "exposure": "0.00"},
        ],
        "vintages": [
            {
                "vintage": "2026-02",
                "loan_count": 1,
                "originated_principal": "6000.00",
                "outstanding_balance": "5000.00",
                "par_30": "100.00",
                "fpd_rate": "100.00",
                "write_off_count": 0,
                "top_up_count": 1,
            },
            {
                "vintage": "2026-01",
                "loan_count": 1,
                "originated_principal": "10000.00",
                "outstanding_balance": "10000.00",
                "par_30": "0.00",
                "fpd_rate": "0.00",
                "write_off_count": 0,
                "top_up_count": 0,
            },
        ],
        "top_up_performance": [
            {
                "label": "New / non-top-up",
                "loan_count": 1,
                "active_exposure": "10000.00",
                "par_30": "0.00",
                "fpd_rate": "0.00",
                "write_off_count": 0,
            },
            {
                "label": "Top-up",
                "loan_count": 1,
                "active_exposure": "5000.00",
                "par_30": "100.00",
                "fpd_rate": "100.00",
                "write_off_count": 0,
            },
        ],
        "top_up_exposure": "5000.00",
        "cdas_exposure": "10000.00",
    }

    assert portfolio._normalized_rust_risk(rust_value) == python_value



def test_polyglot_underwriting_routes_rust_math_and_java_rules() -> None:
    rust = (REPO / "services/compute-rust/src/main.rs").read_text(encoding="utf-8")
    java = (REPO / "services/worker-java/src/main/java/ls/co/loanhub/worker/EventWorker.java").read_text(encoding="utf-8")
    runtime = (ROOT / "services/polyglot_runtime_service.py").read_text(encoding="utf-8")
    affordability = (ROOT / "services/quick_loan_affordability_service.py").read_text(encoding="utf-8")
    benchmark = (ROOT / "services/polyglot_benchmark_service.py").read_text(encoding="utf-8")
    env = (REPO / ".env.example").read_text(encoding="utf-8")

    assert '"/v1/affordability-assessment"' in rust
    assert "struct AffordabilityAssessmentRequest" in rust
    assert "fn affordability_assessment(" in rust
    assert '"/v1/underwriting/rules"' in java
    assert "underwritingRules(" in java
    assert "BigDecimal" in java
    assert "def rust_affordability_assessment(" in runtime
    assert "def java_underwriting_rules(" in runtime
    assert 'workload_routing_mode("rust_affordability")' in affordability
    assert 'workload_routing_mode("java_underwriting_rules")' in affordability
    assert 'record_parity_mismatch("rust_compute")' in affordability
    assert 'record_parity_mismatch("java_worker")' in affordability
    assert '"rust_affordability": 100.0' in benchmark
    assert '"java_underwriting_rules": 100.0' in benchmark
    assert "LOANHUB_RUST_AFFORDABILITY_MODE=shadow" in env
    assert "LOANHUB_JAVA_UNDERWRITING_MODE=shadow" in env


def test_polyglot_language_roles_are_not_decorative() -> None:
    architecture = (REPO / "docs/POLYGLOT_WORK_SHARING.md").read_text(encoding="utf-8")
    go = (REPO / "services/worker-go/main.go").read_text(encoding="utf-8")
    native = (REPO / "services/native-cpp/src/main.cpp").read_text(encoding="utf-8")
    rust = (REPO / "services/compute-rust/src/main.rs").read_text(encoding="utf-8")

    assert "deterministic affordability math" in architecture
    assert "deterministic underwriting/business-rule evaluation" in architecture
    assert "bounded concurrent network/background work" in architecture
    assert "exact integer-cents numerical kernels" in architecture
    assert "sync.WaitGroup" in go
    assert "/v1/webhooks/deliver-batch" in go
    assert "simple-interest" in native
    assert "round_ratio_half_up" in native
    assert "cpp_simple_interest_cents(" in rust


def test_rust_predictive_risk_batch_is_shadow_routed() -> None:
    rust = (REPO / "services/compute-rust/src/main.rs").read_text(encoding="utf-8")
    runtime = (ROOT / "services/polyglot_runtime_service.py").read_text(encoding="utf-8")
    predictive = (ROOT / "services/predictive_intelligence_service.py").read_text(encoding="utf-8")
    env = (REPO / ".env.example").read_text(encoding="utf-8")

    assert '"/v1/predictive-signal-batch"' in rust
    assert "struct PredictiveSignalBatchRequest" in rust
    assert "fn predictive_signal_batch(" in rust
    assert '"rust_predictive_risk": "shadow"' in runtime
    assert "def rust_predictive_signal_batch(" in runtime
    assert 'workload_routing_mode("rust_predictive_risk")' in predictive
    assert 'record_parity_mismatch("rust_compute")' in predictive
    assert "LOANHUB_RUST_PREDICTIVE_RISK_MODE=shadow" in env


def test_predictive_rust_row_contract_matches_python_rules() -> None:
    from types import SimpleNamespace
    from uuid import uuid4

    from services import predictive_intelligence_service as predictive

    loan_id = uuid4()
    current = SimpleNamespace(
        loan_id=loan_id,
        days_past_due=12,
        delinquency_bucket="8-30",
        first_payment_default=True,
        is_top_up=True,
    )
    previous = SimpleNamespace(
        days_past_due=2,
        delinquency_bucket="1-7",
    )
    work_item = SimpleNamespace(
        priority="high",
        priority_score="75",
    )

    rows = predictive._rust_predictive_rows(
        [current],
        {loan_id: previous},
        {loan_id: work_item},
    )

    assert rows == [
        {
            "key": str(loan_id),
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

    normalized = predictive._normalized_rust_signal(
        {
            "risk_score": "74",
            "risk_band": "high",
            "projected_par30_entry": True,
            "stress_bucket_30d": "31-60",
            "rationale": [
                "Loan is already 12 days past due",
                "DPD increased by 10 days since the prior stored snapshot",
                "Delinquency bucket worsened from 1-7 to 8-30",
                "First-payment-default evidence is present",
                "This is a top-up exposure already showing repayment stress",
                "Collections already has a high-priority work item",
            ],
            "recommended_action": "Review the loan and active collection evidence now, then assign or reprioritise the appropriate human recovery action.",
        }
    )
    python_value = predictive._score_signal(current, previous, work_item)

    assert normalized == python_value


def test_predictive_prefer_worker_avoids_python_scoring_when_rust_row_is_valid() -> None:
    service = (ROOT / "services/predictive_intelligence_service.py").read_text(encoding="utf-8")

    assert 'routing_mode == "prefer-worker" and delegated_tuple is not None' in service
    assert "rust_used_count += 1" in service
    assert "python_tuple = _score_signal(current, previous, work_item)" in service
    assert '"promoted_no_live_parity"' in service


def test_go_push_delivery_is_side_effect_safe_and_python_scoped() -> None:
    go = (REPO / "services/worker-go/main.go").read_text(encoding="utf-8")
    runtime = (ROOT / "services/polyglot_runtime_service.py").read_text(encoding="utf-8")
    push = (ROOT / "services/mobile_push_service.py").read_text(encoding="utf-8")
    env = (REPO / ".env.example").read_text(encoding="utf-8")

    assert '"/v1/push/deliver-batch"' in go
    assert "pushConcurrency()" in go
    assert "validProjectID(" in go
    assert '"go_push_delivery": "off"' in runtime
    assert "def go_push_delivery_batch(" in runtime
    assert 'workload_routing_mode("go_push_delivery") == "prefer-worker"' in push
    assert "Side-effecting push delivery is never dual-sent in shadow mode." in push
    assert "LOANHUB_GO_PUSH_DELIVERY_MODE=off" in env


def test_go_push_preparation_keeps_recipient_policy_in_python(monkeypatch) -> None:
    from services import mobile_push_service as push

    event = {
        "event_id": "evt-1",
        "type": "CHAT_MESSAGE_CREATED",
        "domain": "chat",
        "entity_id": "conv-1",
        "conversation_id": "conv-1",
        "message": {
            "sender": {"id": "sender", "display_name": "Koetlisi"},
            "message_type": "text",
            "body": "Hello",
        },
    }

    notification = push._notification_for_recipient(event, "recipient")
    assert notification is not None
    title, body, channel_id, data = push._push_data(event, notification)

    assert title == "Koetlisi"
    assert body == "Hello"
    assert channel_id == "loanhub_messages"
    assert data["event_id"] == "evt-1"
    assert data["route"] == "chat:conv-1"


def test_go_push_handoff_does_not_fallback_after_ambiguous_batch(monkeypatch) -> None:
    from services import mobile_push_service as push

    monkeypatch.setattr(push, "_firebase_access_token", lambda: ("loanhub-prod", "short-lived-token"))

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(push, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(push, "_active_tokens", lambda db, ids: ["token-1", "token-2"])
    monkeypatch.setattr(
        push,
        "_notification_for_recipient",
        lambda event, recipient_id: {
            "category": "message",
            "title": "LoanHub",
            "body": "Update",
            "route": "inbox",
        },
    )
    calls = {"count": 0}

    def ambiguous(**kwargs):
        calls["count"] += 1
        return None

    monkeypatch.setattr(push, "go_push_delivery_batch", ambiguous)

    assert push._send_sync_go(["user-1"], {"event_id": "evt-1"}) is False
    assert calls["count"] == 1
