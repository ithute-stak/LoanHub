from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerStatus:
    name: str
    configured: bool
    ready: bool
    detail: str | None = None


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


def worker_statuses() -> list[WorkerStatus]:
    results: list[WorkerStatus] = []
    for name, base_url in [
        ("rust_compute", rust_compute_url()),
        ("go_worker", go_worker_url()),
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
    try:
        return _get_json(f"{base_url}/v1/affordability-headroom?{query}")
    except (OSError, ValueError, urllib.error.URLError):
        return None


def go_digest(
    *,
    correlation_id: str,
    payload: str,
) -> dict | None:
    """Ask the Go worker for a replayable SHA-256 digest job."""
    base_url = go_worker_url()
    if not base_url:
        return None
    try:
        return _post_json(
            f"{base_url}/v1/digest",
            {"correlation_id": correlation_id, "payload": payload},
        )
    except (OSError, ValueError, urllib.error.URLError):
        return None


def stable_sha256_text(*, correlation_id: str, payload: str) -> str:
    """Delegate replayable text hashing to Go when available, otherwise use Python."""
    result = go_digest(correlation_id=correlation_id, payload=payload)
    candidate = str((result or {}).get("sha256") or "").lower()
    if len(candidate) == 64 and all(ch in "0123456789abcdef" for ch in candidate):
        return candidate
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
    try:
        value = _get_json(f"{base_url}/v1/variance-classification?{query}")
    except (OSError, ValueError, urllib.error.URLError):
        return None
    if value.get("status") not in {"matched", "shortage", "excess"}:
        return None
    try:
        value["variance_cents"] = int(value["variance_cents"])
    except (KeyError, TypeError, ValueError):
        return None
    return value
