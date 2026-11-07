"""Offline-only integrity gate for archived Batlokoa financial engine contracts.

No financial calls, network access, DB connections, API imports or migrations.
Run from repository root: python docs/reference/batlokoa_phase35/verify_reference.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
EXPECTED = {
    "financial_allocation.py": ("def propose_allocation", "class AllocationError"),
    "double_entry.py": ("def validate_journal", "def propose_received_collection_journal"),
    "payment_lifecycle.py": ("def apply_event", "class InvalidTransition"),
    "provider_evidence.py": ("def verify_test_provider_evidence", "class EvidenceError"),
    "reconciliation.py": ("def reconcile", "class MatchStatus"),
    "idempotency_contract.py": ("def classify_reused_key", "class KeyDecision"),
    "postgres_reservation.py": ("ON CONFLICT (company_id, idempotency_key) DO NOTHING", "FOR UPDATE"),
    "wire_contract_reference.py": ("def signed_test_vector", "def verify_test_vector"),
    "test_payment_lifecycle.py": ("class LifecycleContractTests",),
    "test_financial_engine.py": ("class FinancialContractTests",),
    "test_postgres_reservation.py": ("def test_created_repeat_conflict",),
    "test_wire_contract_reference.py": ("class ContractTests",),
    "01_collection_intent_reservation.sql": ("CREATE TABLE IF NOT EXISTS", "UNIQUE (company_id, idempotency_key)"),
    "02_reservation_rls_draft.sql": ("DESIGN DRAFT ONLY", "FORCE ROW LEVEL SECURITY"),
    "README.md": ("not installed", "No",),
}
issues: list[str] = []
for name, markers in EXPECTED.items():
    path = ROOT / name
    if not path.is_file():
        issues.append(f"Missing: {name}")
        continue
    source = path.read_text(encoding="utf-8")
    if name.endswith(".py"):
        try:
            ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            issues.append(f"Syntax: {name}: {exc.msg}")
    for marker in markers:
        if marker not in source:
            issues.append(f"Missing marker {marker!r} in {name}")

# Never allow archived financial source to be loaded by runtime via API routes.
api_router = ROOT.parents[2] / "apps" / "backend" / "api" / "v1" / "router.py"
if api_router.is_file() and "batlokoa_phase35" in api_router.read_text(encoding="utf-8"):
    issues.append("Archived financial engine was referenced by active API router")
if issues:
    print("\n".join(issues), file=sys.stderr)
    sys.exit(1)
print(f"Offline Batlokoa reference gate PASS: {len(EXPECTED)} required files and syntax/markers checked")
