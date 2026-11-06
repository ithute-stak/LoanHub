"""Strict local STU-compatible stroke envelope validation.

Input must be emitted by an explicitly installed native capture adapter after
visible signer confirmation. This module does not claim to control Wacom SDK.
It rejects unbounded streams, spoofed metadata, and empty pen gestures.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass

MAX_BYTES = 128_000
MAX_STROKES = 128
MAX_POINTS = 8192
CAPTURE_FORMAT = "loanhub-pen-strokes-v1"


@dataclass(frozen=True)
class CaptureEnvelope:
    canonical: bytes
    stroke_count: int
    point_count: int


def validate_strokes(raw: bytes) -> CaptureEnvelope:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Pen stroke payload exceeds supported bounds")
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid pen stroke JSON") from exc
    if not isinstance(value, dict) or set(value) != {"format", "strokes"}:
        raise ValueError("Unexpected pen stroke fields")
    if value["format"] != CAPTURE_FORMAT:
        raise ValueError("Unknown capture format")
    strokes = value["strokes"]
    if not isinstance(strokes, list) or not 1 <= len(strokes) <= MAX_STROKES:
        raise ValueError("Invalid stroke count")
    total = 0
    normalized = []
    for stroke in strokes:
        if not isinstance(stroke, list) or not 2 <= len(stroke) <= MAX_POINTS:
            raise ValueError("Every stroke must contain at least two points")
        output = []
        last_t = -1
        for point in stroke:
            if not isinstance(point, dict) or set(point) != {"x", "y", "pressure", "t"}:
                raise ValueError("Invalid point attributes")
            x, y, pressure, tick = (point[k] for k in ("x", "y", "pressure", "t"))
            for item in (x, y, pressure):
                if type(item) not in (int, float) or not math.isfinite(item):
                    raise ValueError("Non-finite or invalid coordinate")
            if type(tick) is not int or tick <= last_t or tick < 0 or tick > 300000:
                raise ValueError("Invalid point time sequence")
            if not 0 <= x <= 1 or not 0 <= y <= 1 or not 0 <= pressure <= 1:
                raise ValueError("Out-of-bounds pen coordinate or pressure")
            last_t = tick
            output.append({"x": x, "y": y, "pressure": pressure, "t": tick})
        normalized.append(output)
        total += len(output)
        if total > MAX_POINTS:
            raise ValueError("Too many pen points")
    canonical = json.dumps({"format": CAPTURE_FORMAT, "strokes": normalized},
                           separators=(",", ":"), sort_keys=True,
                           allow_nan=False).encode("utf-8")
    if len(canonical) > MAX_BYTES:
        raise ValueError("Normalized capture too large")
    return CaptureEnvelope(canonical, len(normalized), total)
