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

    digest = "a" * 64
    monkeypatch.setenv("LOANHUB_GO_WORKER_URL", "http://go-worker:8081")
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
    assert 'delegated_status or (' in service
    assert '"matched" if variance == 0 else "shortage" if variance < 0 else "excess"' in service


def test_rust_loan_preview_is_used_only_after_python_parity(monkeypatch) -> None:
    from datetime import date
    from decimal import Decimal

    from database.models.enums import LoanCalculationMethod
    from services import interest_calculation_service as interest

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
        "rust_parity": "passed",
        "cpp_used": False,
        "fallback": False,
    }


def test_rust_loan_preview_mismatch_falls_back_to_python(monkeypatch) -> None:
    from datetime import date
    from decimal import Decimal

    from database.models.enums import LoanCalculationMethod
    from services import interest_calculation_service as interest

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
    assert "LoanCalculationMethod.REDUCING_BALANCE" not in service.split("rust_supported =", 1)[1].split("}", 1)[0]
    assert "LoanCalculationMethod.DAILY_ACCRUAL_REDUCING" not in service.split("rust_supported =", 1)[1].split("}", 1)[0]


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
