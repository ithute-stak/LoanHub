"""Validation primitives for future Wacom/browser contract signing evidence.

No contract is marked signed here. Server-side authorization, consent, persisted
one-time sessions, encryption and PDF finalization must be implemented separately.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException

MAX_STROKES = 300
MAX_POINTS = 10000
MAX_DURATION_MS = 120000
MAX_IMAGE_BYTES = 512000
CAPTURE_WIDTH = 640
CAPTURE_HEIGHT = 240


def validate_capture(
    *,
    expected_contract_id: UUID,
    contract_id: UUID,
    contract_hash: str,
    expected_contract_hash: str,
    strokes: Any,
    input_method: str,
) -> dict[str, Any]:
    """Reject oversized, cross-contract or malformed pen strokes.

    The result is a canonical digest for *candidate* capture evidence, not
    evidence of consent/identity, and cannot be used alone to sign a contract.
    """
    if contract_id != expected_contract_id or contract_hash != expected_contract_hash:
        raise HTTPException(409, "Signature capture does not match this contract")
    if len(expected_contract_hash) != 64 or any(c not in "0123456789abcdef" for c in expected_contract_hash):
        raise HTTPException(409, "Invalid canonical contract hash")
    if input_method not in {"pointer", "wacom_stu"}:
        raise HTTPException(422, "Unsupported capture source")
    if not isinstance(strokes, list) or not 1 <= len(strokes) <= MAX_STROKES:
        raise HTTPException(422, "Invalid stroke count")
    normalized = []
    total = 0
    timestamps = []
    for stroke in strokes:
        if not isinstance(stroke, list) or not stroke:
            raise HTTPException(422, "Empty or invalid stroke")
        points = []
        for point in stroke:
            total += 1
            if total > MAX_POINTS or not isinstance(point, dict):
                raise HTTPException(422, "Invalid capture point")
            if set(point) != {"x", "y", "at", "pressure"}:
                raise HTTPException(422, "Unexpected capture point attributes")
            values = [point[k] for k in ("x", "y", "at", "pressure")]
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
                raise HTTPException(422, "Nonfinite capture point")
            x, y, at, pressure = values
            if not (0 <= x <= CAPTURE_WIDTH and 0 <= y <= CAPTURE_HEIGHT and 0 <= pressure <= 1):
                raise HTTPException(422, "Capture point outside accepted bounds")
            if not isinstance(at, int) or at < 0:
                raise HTTPException(422, "Invalid capture timestamp")
            if timestamps and at < timestamps[-1]:
                raise HTTPException(422, "Capture timestamps are not monotonic")
            timestamps.append(at)
            points.append({"x": round(x, 3), "y": round(y, 3), "at": at, "pressure": round(pressure, 3)})
        normalized.append(points)
    if len(timestamps) < 2 or timestamps[-1] - timestamps[0] > MAX_DURATION_MS:
        raise HTTPException(422, "Insufficient or overly long signature capture")
    canonical = {
        "contract_id": str(contract_id),
        "contract_hash": expected_contract_hash,
        "input_method": input_method,
        "strokes": normalized,
    }
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"sha256": digest, "stroke_count": len(normalized), "point_count": total, "captured_at": datetime.now(timezone.utc).isoformat()}
