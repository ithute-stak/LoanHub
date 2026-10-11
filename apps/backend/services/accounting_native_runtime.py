"""Opt-in, read-only native accounting bridge for diagnostic parity.

The bridge does not connect to the database and never authorizes posting.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path

from services.accounting_native_parity import compare_trial_balance


def native_accounting_execute(command: str, payload: str) -> str | None:
    """Execute only supported read-only C++ accounting commands."""
    if command not in {"accounting-trial-balance", "accounting-journal-validate"}:
        raise ValueError("unsupported accounting command")
    library_path = os.environ.get("LOANHUB_CPP_LIBRARY_PATH")
    if not library_path:
        return None
    try:
        library = ctypes.CDLL(str(Path(library_path)))
        execute = library.loanhub_native_execute
        execute.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t
        ]
        execute.restype = ctypes.c_int
        encoded = payload.encode("utf-8")
        capacity = max(65536, len(encoded) * 4)
        for _ in range(5):
            if capacity > 32 * 1024 * 1024:
                return None
            output = ctypes.create_string_buffer(capacity)
            written = execute(command.encode("ascii"), encoded, output, capacity)
            if written >= 0:
                if written >= capacity:
                    return None
                return output.raw[:written].decode("utf-8")
            if written != -2:
                return None
            capacity *= 2
    except (OSError, AttributeError, UnicodeDecodeError, ValueError):
        return None
    return None


def advisory_trial_balance(rows):
    """Compare with Python reference; no side effects and no ledger writes."""
    return compare_trial_balance(rows, native_accounting_execute)
