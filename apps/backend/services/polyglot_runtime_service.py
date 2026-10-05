from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from threading import Lock
from time import monotonic


@dataclass(frozen=True)
class WorkerStatus:
    name: str
    configured: bool
    ready: bool
    detail: str | None = None


_CIRCUIT_FAILURE_THRESHOLD = 3
_CIRCUIT_OPEN_SECONDS = 30.0
_runtime_lock = Lock()
_runtime_state: dict[str, dict[str, float | int | str | None]] = {}

_ROUTING_ENV = {
    "go_reconciliation_hash": "LOANHUB_GO_RECON_HASH_MODE",
    "rust_reconciliation": "LOANHUB_RUST_RECON_MODE",
    "rust_loan_calculation": "LOANHUB_RUST_LOAN_CALC_MODE",
    "java_event_processing": "LOANHUB_JAVA_EVENT_MODE",
}
_ROUTING_DEFAULTS = {
    "go_reconciliation_hash": "prefer-worker",
    "rust_reconciliation": "prefer-worker",
    "rust_loan_calculation": "shadow",
    "java_event_processing": "shadow",
}
_ROUTING_MODES = {"off", "shadow", "prefer-worker"}


def workload_routing_mode(workload: str) -> str:
    env_name = _ROUTING_ENV.get(workload)
    default = _ROUTING_DEFAULTS.get(workload, "shadow")
    if not env_name:
        return default
    value = os.getenv(env_name, default).strip().lower()
    return value if value in _ROUTING_MODES else default


def routing_snapshot() -> dict[str, dict[str, str]]:
    return {
        workload: {
            "mode": workload_routing_mode(workload),
            "env": env_name,
        }
        for workload, env_name in _ROUTING_ENV.items()
    }


def _state(name: str) -> dict[str, float | int | str | None]:
    with _runtime_lock:
        return _runtime_state.setdefault(
            name,
            {
                "calls": 0,
                "successes": 0,
                "failures": 0,
                "fallbacks": 0,
                "parity_mismatches": 0,
                "consecutive_failures": 0,
                "circuit_open_until": 0.0,
                "last_latency_ms": None,
                "last_error": None,
            },
        )


def _worker_allowed(name: str) -> bool:
    state = _state(name)
    return float(state.get("circuit_open_until") or 0.0) <= monotonic()


def _record_success(name: str, started: float) -> None:
    with _runtime_lock:
        state = _runtime_state.setdefault(name, {})
        state["calls"] = int(state.get("calls") or 0) + 1
        state["successes"] = int(state.get("successes") or 0) + 1
        state["consecutive_failures"] = 0
        state["circuit_open_until"] = 0.0
        state["last_latency_ms"] = round((monotonic() - started) * 1000, 3)
        state["last_error"] = None


def _record_failure(name: str, started: float, error: BaseException | str) -> None:
    with _runtime_lock:
        state = _runtime_state.setdefault(name, {})
        state["calls"] = int(state.get("calls") or 0) + 1
        state["failures"] = int(state.get("failures") or 0) + 1
        state["fallbacks"] = int(state.get("fallbacks") or 0) + 1
        consecutive = int(state.get("consecutive_failures") or 0) + 1
        state["consecutive_failures"] = consecutive
        state["last_latency_ms"] = round((monotonic() - started) * 1000, 3)
        state["last_error"] = type(error).__name__ if isinstance(error, BaseException) else str(error)[:120]
        if consecutive >= _CIRCUIT_FAILURE_THRESHOLD:
            state["circuit_open_until"] = monotonic() + _CIRCUIT_OPEN_SECONDS


def record_parity_mismatch(name: str) -> None:
    with _runtime_lock:
        state = _runtime_state.setdefault(name, {})
        state["parity_mismatches"] = int(state.get("parity_mismatches") or 0) + 1
        state["fallbacks"] = int(state.get("fallbacks") or 0) + 1


def runtime_metrics() -> dict[str, dict[str, float | int | str | bool | None]]:
    now = monotonic()
    with _runtime_lock:
        snapshot = {}
        for name, state in _runtime_state.items():
            open_until = float(state.get("circuit_open_until") or 0.0)
            snapshot[name] = {
                "calls": int(state.get("calls") or 0),
                "successes": int(state.get("successes") or 0),
                "failures": int(state.get("failures") or 0),
                "fallbacks": int(state.get("fallbacks") or 0),
                "parity_mismatches": int(state.get("parity_mismatches") or 0),
                "consecutive_failures": int(state.get("consecutive_failures") or 0),
                "circuit_open": open_until > now,
                "circuit_retry_in_seconds": round(max(0.0, open_until - now), 3),
                "last_latency_ms": state.get("last_latency_ms"),
                "last_error": state.get("last_error"),
            }
        return snapshot


def _guarded_get_json(name: str, url: str, timeout: float) -> dict | None:
    if not _worker_allowed(name):
        with _runtime_lock:
            state = _runtime_state.setdefault(name, {})
            state["fallbacks"] = int(state.get("fallbacks") or 0) + 1
        return None
    started = monotonic()
    try:
        value = _get_json(url, timeout=timeout)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        _record_failure(name, started, exc)
        return None
    _record_success(name, started)
    return value


def _guarded_post_json(name: str, url: str, payload: dict, timeout: float) -> dict | None:
    if not _worker_allowed(name):
        with _runtime_lock:
            state = _runtime_state.setdefault(name, {})
            state["fallbacks"] = int(state.get("fallbacks") or 0) + 1
        return None
    started = monotonic()
    try:
        value = _post_json(url, payload, timeout=timeout)
    except (OSError, TypeError, ValueError, urllib.error.URLError) as exc:
        _record_failure(name, started, exc)
        return None
    _record_success(name, started)
    return value


def _get_json(url: str, timeout: float = 0.8) -> dict:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read(64 * 1024)
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("worker response must be an object")
    return value


def _post_json(url: str, payload: dict, timeout: float = 1.0) -> dict:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=raw,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(64 * 1024)
    value = json.loads(body.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("worker response must be an object")
    return value


def rust_compute_url() -> str:
    return os.getenv("LOANHUB_RUST_COMPUTE_URL", "").rstrip("/")


def go_worker_url() -> str:
    return os.getenv("LOANHUB_GO_WORKER_URL", "").rstrip("/")


def java_worker_url() -> str:
    return os.getenv("LOANHUB_JAVA_WORKER_URL", "").rstrip("/")


def worker_statuses() -> list[WorkerStatus]:
    results: list[WorkerStatus] = []
    for name, base_url in [
        ("rust_compute", rust_compute_url()),
        ("go_worker", go_worker_url()),
        ("java_worker", java_worker_url()),
    ]:
        if not base_url:
            results.append(WorkerStatus(name=name, configured=False, ready=False))
            continue
        try:
            payload = _get_json(f"{base_url}/health/ready")
            results.append(
                WorkerStatus(
                    name=name,
                    configured=True,
                    ready=payload.get("status") == "ready",
                    detail=str(payload.get("runtime") or ""),
                )
            )
        except (OSError, ValueError, urllib.error.URLError) as exc:
            results.append(
                WorkerStatus(
                    name=name,
                    configured=True,
                    ready=False,
                    detail=type(exc).__name__,
                )
            )
    return results


def rust_affordability_headroom_preview(
    *,
    income_cents: int,
    commitments_cents: int,
    proposed_cents: int,
) -> dict | None:
    """Optional non-authoritative acceleration.

    A missing/unhealthy Rust worker returns None so callers keep using Python.
    """
    base_url = rust_compute_url()
    if not base_url:
        return None
    query = urllib.parse.urlencode(
        {
            "income_cents": int(income_cents),
            "commitments_cents": int(commitments_cents),
            "proposed_cents": int(proposed_cents),
        }
    )
    return _guarded_get_json(
        "rust_compute",
        f"{base_url}/v1/affordability-headroom?{query}",
        timeout=0.8,
    )


def go_digest(
    *,
    correlation_id: str,
    payload: str,
) -> dict | None:
    """Ask the Go worker for a replayable SHA-256 digest job."""
    base_url = go_worker_url()
    if not base_url:
        return None
    return _guarded_post_json(
        "go_worker",
        f"{base_url}/v1/digest",
        {"correlation_id": correlation_id, "payload": payload},
        timeout=1.0,
    )


def stable_sha256_text(*, correlation_id: str, payload: str) -> str:
    """Parity-check replayable hashing before accepting Go work."""
    python_digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    mode = workload_routing_mode("go_reconciliation_hash")
    if mode == "off":
        return python_digest

    result = go_digest(correlation_id=correlation_id, payload=payload)
    candidate = str((result or {}).get("sha256") or "").lower()
    valid = (
        len(candidate) == 64
        and all(ch in "0123456789abcdef" for ch in candidate)
        and candidate == python_digest
    )
    if not valid:
        if result is not None:
            record_parity_mismatch("go_worker")
        return python_digest
    if mode == "shadow":
        return python_digest
    return candidate


def rust_variance_classification(
    *,
    expected_cents: int,
    actual_cents: int,
) -> dict | None:
    """Delegate deterministic reconciliation variance classification to Rust."""
    base_url = rust_compute_url()
    if not base_url:
        return None
    query = urllib.parse.urlencode(
        {
            "expected_cents": int(expected_cents),
            "actual_cents": int(actual_cents),
        }
    )
    value = _guarded_get_json(
        "rust_compute",
        f"{base_url}/v1/variance-classification?{query}",
        timeout=0.8,
    )
    if value is None:
        return None
    if value.get("status") not in {"matched", "shortage", "excess"}:
        return None
    try:
        value["variance_cents"] = int(value["variance_cents"])
    except (KeyError, TypeError, ValueError):
        return None
    return value


def rust_loan_preview(
    *,
    method: str,
    principal: str,
    rate_percent: str,
    term_months: int,
    processing_fee: str,
    interest_start_date: str,
    due_dates: list[str],
) -> dict | None:
    """Ask Rust to compute a non-authoritative loan preview for parity checking."""
    base_url = rust_compute_url()
    if not base_url:
        return None
    value = _guarded_post_json(
        "rust_compute",
        f"{base_url}/v1/loan-preview",
        {
            "method": method,
            "principal": principal,
            "rate_percent": rate_percent,
            "term_months": int(term_months),
            "processing_fee": processing_fee,
            "interest_start_date": interest_start_date,
            "due_dates": list(due_dates),
        },
        timeout=1.5,
    )
    if value is None:
        return None
    if value.get("authoritative") is not False:
        return None
    if value.get("method") != method:
        return None
    if not isinstance(value.get("schedule_amounts"), list):
        return None
    return value


def java_canonicalize_event(
    *,
    correlation_id: str,
    event_type: str,
    payload: dict,
) -> dict | None:
    """Delegate non-authoritative enterprise event canonicalization to Java."""
    base_url = java_worker_url()
    if not base_url:
        return None
    value = _guarded_post_json(
        "java_worker",
        f"{base_url}/v1/events/canonicalize",
        {
            "correlation_id": correlation_id,
            "event_type": event_type,
            "payload": payload,
        },
        timeout=1.5,
    )
    if value is None:
        return None
    if value.get("authoritative") is not False:
        return None
    if value.get("correlation_id") != correlation_id:
        return None
    if value.get("event_type") != event_type:
        return None
    if not isinstance(value.get("canonical_json"), str):
        return None
    if not isinstance(value.get("payload_sha256"), str):
        return None
    return value


def java_event_batch_summary(*, events: list[dict]) -> dict | None:
    """Ask Java to summarize replayable event batches for operational analytics."""
    base_url = java_worker_url()
    if not base_url:
        return None
    value = _guarded_post_json(
        "java_worker",
        f"{base_url}/v1/events/batch-summary",
        {"events": events},
        timeout=1.5,
    )
    if value is None:
        return None
    if value.get("authoritative") is not False:
        return None
    if not isinstance(value.get("counts_by_type"), dict):
        return None
    return value
