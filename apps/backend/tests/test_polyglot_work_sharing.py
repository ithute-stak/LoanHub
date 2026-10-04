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
    assert '"authoritative":false' in rust
    assert "/health/ready" in go
    assert "/v1/digest" in go
    assert "Native kernel boundary" in native
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
