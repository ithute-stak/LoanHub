from uuid import UUID

import pytest
from fastapi import HTTPException

from services.pad_signature_evidence import validate_capture

CONTRACT_ID = UUID("11111111-2222-3333-4444-555555555555")
HASH = "a" * 64


def valid_strokes():
    return [[
        {"x": 2, "y": 6, "at": 1000, "pressure": 0.5},
        {"x": 5, "y": 9, "at": 1020, "pressure": 0.6},
    ]]


def capture(**overrides):
    data = dict(
        expected_contract_id=CONTRACT_ID,
        contract_id=CONTRACT_ID,
        expected_contract_hash=HASH,
        contract_hash=HASH,
        strokes=valid_strokes(),
        input_method="pointer",
    )
    data.update(overrides)
    return validate_capture(**data)


def test_capture_hash_is_bound_to_contract_and_strokes():
    a = capture()
    b = capture()
    assert a["sha256"] == b["sha256"]
    assert a["point_count"] == 2
    assert capture(input_method="wacom_stu")["sha256"] != a["sha256"]


@pytest.mark.parametrize("field,value", [
    ("contract_id", UUID("99999999-2222-3333-4444-555555555555")),
    ("contract_hash", "b" * 64),
    ("input_method", "forged_usb"),
    ("strokes", []),
    ("strokes", [[{"x": 1, "y": 2, "at": 1000, "pressure": 1}]]),
    ("strokes", [[{"x": -1, "y": 2, "at": 1000, "pressure": 1}, {"x": 2, "y": 3, "at": 1001, "pressure": 1}]]),
    ("strokes", [[{"x": float("nan"), "y": 2, "at": 1000, "pressure": 1}, {"x": 2, "y": 3, "at": 1001, "pressure": 1}]]),
    ("strokes", [[{"x": 1, "y": 2, "at": 1001, "pressure": 1}, {"x": 2, "y": 3, "at": 1000, "pressure": 1}]]),
    ("strokes", [[{"x": 1, "y": 2, "at": 0, "pressure": 1}, {"x": 2, "y": 3, "at": 120001, "pressure": 1}]]),
])
def test_invalid_capture_is_rejected(field, value):
    with pytest.raises(HTTPException):
        capture(**{field: value})


def test_signature_validation_does_not_modify_contract_or_sign():
    result = capture()
    assert "signed_at" not in result
    assert "contract_status" not in result
