"""Strict signature PNG validation: valid image only, bounded inflation."""
from __future__ import annotations

import struct
import zlib
import pytest
from fastapi import HTTPException

from services.wacom_png_validation import validate_wacom_png
from scripts.wacom_real_api_smoke import synthetic_png


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload)) + kind + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)
    )


def test_valid_synthetic_png_accepted():
    validate_wacom_png(synthetic_png())


def test_signature_header_only_is_not_valid_png():
    with pytest.raises(HTTPException) as exc:
        validate_wacom_png(bytes.fromhex("89504e470d0a1a0a") + b"fake")
    assert exc.value.status_code == 422


@pytest.mark.parametrize("alter", [
    lambda b: b[:-4],
    lambda b: b + b"AFTER-IEND",
    lambda b: b[:25] + bytes([b[25] ^ 1]) + b[26:],
    lambda b: b[:8] + b"123456789" + b[17:],
])
def test_corrupt_crc_and_truncated_png_rejected(alter):
    with pytest.raises(HTTPException):
        validate_wacom_png(alter(synthetic_png()))


def test_oversize_dimensions_rejected():
    base = synthetic_png()
    ihdr = struct.pack(">IIBBBBB", 99999, 8, 8, 6, 0, 0, 0)
    modified = base[:8] + png_chunk(b"IHDR", ihdr) + base[33:]
    with pytest.raises(HTTPException):
        validate_wacom_png(modified)


def test_bad_zlib_content_rejected():
    base = synthetic_png()
    ihdr_end = 33
    idat_length = struct.unpack(">I", base[ihdr_end:ihdr_end+4])[0]
    end = ihdr_end + 12 + idat_length
    modified = base[:ihdr_end] + png_chunk(b"IDAT", b"garbage") + base[end:]
    with pytest.raises(HTTPException):
        validate_wacom_png(modified)


def test_decompression_bomb_rejected():
    width, height = 16, 8
    ihdr = struct.pack(">IIBBBBB",width,height,8,6,0,0,0)
    payload = zlib.compress(b"\x00" * 1_000_000)
    crafted = (
        bytes.fromhex("89504e470d0a1a0a")
        + png_chunk(b"IHDR",ihdr)
        + png_chunk(b"IDAT",payload)
        + png_chunk(b"IEND",b"")
    )
    with pytest.raises(HTTPException):
        validate_wacom_png(crafted)


def test_metadata_and_animated_chunks_rejected():
    base = synthetic_png()
    for forbidden in (b"iCCP", b"tRNS", b"acTL", b"eXIf"):
        crafted = base[:33] + png_chunk(forbidden,b"data") + base[33:]
        with pytest.raises(HTTPException):
            validate_wacom_png(crafted)
