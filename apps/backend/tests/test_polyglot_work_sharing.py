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
