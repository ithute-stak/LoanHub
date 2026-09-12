#!/usr/bin/env python3
"""Audit literal frontend API calls against the assembled FastAPI application.

Run from apps/backend after the normal environment variables are available:

    python scripts/audit_route_contracts.py --frontend-root ../frontend

The audit intentionally checks literal URL calls. Dynamic paths are validated by
OpenAPI and focused integration tests because their concrete values are only
known at runtime.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from fastapi.routing import APIRoute

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

API_CALL_PATTERN = re.compile(
    r"api\.(get|post|put|patch|delete)\s*"
    r"(?:<[^>]+>)?\s*\(\s*([\"'`])(/[^\"'`]+)\2"
)

CRITICAL_ROUTES = {
    ("GET", "/api/v1/analytics/company"),
    ("GET", "/api/v1/analytics/platform"),
    ("GET", "/api/v1/analytics/borrower"),
    ("POST", "/api/v1/loans/calculator"),
    ("GET", "/api/v1/lending-operations/dashboard"),
    ("POST", "/api/v1/lending-operations/cdas/mandates"),
    ("POST", "/api/v1/lending-operations/reconciliation/run"),
    ("POST", "/api/v1/lending-operations/credit-bureau/enquiries"),
    ("POST", "/api/v1/lending-operations/compliance/cases"),
    ("POST", "/api/v1/lending-operations/collections/cases"),
    ("POST", "/api/v1/lending-operations/regulatory/submissions"),
    ("POST", "/api/v1/lending-operations/decisions/evaluate"),
}


def route_pattern(path: str) -> re.Pattern[str]:
    escaped = re.escape(path)
    escaped = re.sub(r"\\\{[^}]+\\\}", r"[^/]+", escaped)
    return re.compile(f"^{escaped}/?$")


def registered_operations() -> list[tuple[str, re.Pattern[str], str]]:
    from main import app

    operations: list[tuple[str, re.Pattern[str], str]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        pattern = route_pattern(route.path)
        for method in route.methods or set():
            if method in {"HEAD", "OPTIONS"}:
                continue
            operations.append((method.upper(), pattern, route.path))
    return operations


def normalize_frontend_url(url: str) -> str:
    clean = urlsplit(url).path
    if clean.startswith("/api/v1/"):
        return clean
    return f"/api/v1{clean}"


def scan_frontend(frontend_root: Path):
    for path in frontend_root.rglob("*"):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        if any(part in {"node_modules", ".next"} for part in path.parts):
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        for method, _quote, url in API_CALL_PATTERN.findall(source):
            if "${" in url:
                continue
            yield path, method.upper(), normalize_frontend_url(url)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--frontend-root",
        type=Path,
        default=PROJECT_ROOT.parent / "frontend",
    )
    args = parser.parse_args()
    frontend_root = args.frontend_root.resolve()
    if not frontend_root.exists():
        raise SystemExit(f"Frontend root not found: {frontend_root}")

    operations = registered_operations()
    exact = {(method, path) for method, _pattern, path in operations}

    missing_critical = sorted(CRITICAL_ROUTES - exact)
    mismatches: list[tuple[str, str, str]] = []
    checked = 0
    for path, method, url in scan_frontend(frontend_root):
        checked += 1
        if not any(
            registered_method == method and pattern.match(url)
            for registered_method, pattern, _registered_path in operations
        ):
            mismatches.append((str(path.relative_to(frontend_root)), method, url))

    if missing_critical or mismatches:
        if missing_critical:
            print("Missing critical backend routes:")
            for method, path in missing_critical:
                print(f"  {method} {path}")
        if mismatches:
            print("Frontend/backend route mismatches:")
            for source, method, url in mismatches:
                print(f"  {source}: {method} {url}")
        raise SystemExit(1)

    print("LoanHub route contract audit passed")
    print(f"Registered backend operations: {len(operations)}")
    print(f"Literal frontend API calls checked: {checked}")
    print(f"Critical routes checked: {len(CRITICAL_ROUTES)}")


if __name__ == "__main__":
    main()
