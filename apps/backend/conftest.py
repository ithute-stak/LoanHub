"""Pytest bootstrap for LoanHub backend imports.

The backend uses top-level imports such as ``database``, ``routers``,
``services`` and ``main``.  When pytest is launched through its console
entry point, the backend directory is not guaranteed to be present on
``sys.path``.  Add it deterministically before test modules are collected.
"""

from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
