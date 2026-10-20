"""Normalize existing employer names without deleting deduction or loan records.

Run inside the backend environment:
  python scripts/normalize_legacy_employers.py
  python scripts/normalize_legacy_employers.py --apply

The default is a read-only preview. Apply requires a database backup and runs
in a single transaction. Tenant boundaries are always respected.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict

from sqlalchemy import select, update, delete
from database.session import SessionLocal
from database.models.legacy_employer import LegacyEmployer
from database.models.legacy_bank_deduction import LegacyBankDeduction


def normalized(value: str | None) -> str:
    return re.sub(r"\\s+", " ", value or "").strip().casefold()


def clean(value: str | None) -> str:
    return re.sub(r"\\s+", " ", value or "").strip()


def plan(directory, deductions):
    """Pure deterministic plan keyed by company and case-insensitive employer."""
    grouped = defaultdict(list)
    for item in directory:
        if normalized(item.name):
            grouped[(str(item.company_id), normalized(item.name))].append(("directory", item))
    for item in deductions:
        if normalized(item.employer):
            grouped[(str(item.company_id), normalized(item.employer))].append(("deduction", item))
    changes = []
    for (company, key), records in sorted(grouped.items()):
        directory_rows = sorted((obj for kind, obj in records if kind == "directory"), key=lambda obj: (obj.created_at.isoformat() if obj.created_at else "", str(obj.id)))
        # Prefer the oldest directory entry, then oldest deduction spelling.
        if directory_rows:
            name = clean(directory_rows[0].name)
            keeper = directory_rows[0]
        else:
            earliest = min((obj for kind, obj in records if kind == "deduction"), key=lambda obj: (obj.created_at.isoformat() if obj.created_at else "", str(obj.id)))
            name = clean(earliest.employer)
            keeper = None
        for kind, obj in records:
            if kind == "deduction" and obj.employer != name:
                changes.append(("rename_deduction", company, str(obj.id), name))
            elif kind == "directory":
                if obj is keeper:
                    if obj.name != name or obj.normalized_name != key:
                        changes.append(("normalize_directory", company, str(obj.id), name, key))
                else:
                    changes.append(("delete_directory_duplicate", company, str(obj.id)))
    return changes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Commit changes; default is dry-run")
    parser.add_argument("--company-id", help="Limit changes to one company UUID")
    args = parser.parse_args()
    with SessionLocal() as db:
        # Lock both tables for apply so concurrent writers cannot create new duplicates.
        if args.apply:
            db.execute(__import__("sqlalchemy").text(
                "LOCK TABLE legacy_employers, legacy_bank_deductions IN SHARE ROW EXCLUSIVE MODE"
            ))
        directory_query = select(LegacyEmployer).order_by(LegacyEmployer.company_id, LegacyEmployer.created_at, LegacyEmployer.id)
        deduction_query = select(LegacyBankDeduction).order_by(LegacyBankDeduction.company_id, LegacyBankDeduction.created_at, LegacyBankDeduction.id)
        if args.company_id:
            from uuid import UUID
            company_id = UUID(args.company_id)
            directory_query = directory_query.where(LegacyEmployer.company_id == company_id)
            deduction_query = deduction_query.where(LegacyBankDeduction.company_id == company_id)
        directory = db.scalars(directory_query).all()
        deductions = db.scalars(deduction_query).all()
        changes = plan(directory, deductions)
        counts = {action: sum(1 for c in changes if c[0] == action)
                  for action in ("rename_deduction", "normalize_directory", "delete_directory_duplicate")}
        print(json.dumps({"mode": "apply" if args.apply else "dry-run", "counts": counts, "companies_affected": len({c[1] for c in changes})}, indent=2))
        if args.apply:
            from uuid import UUID
            for action, company, row_id, *values in changes:
                if action == "rename_deduction":
                    db.execute(update(LegacyBankDeduction).where(LegacyBankDeduction.id == UUID(row_id), LegacyBankDeduction.company_id == UUID(company)).values(employer=values[0]))
                elif action == "delete_directory_duplicate":
                    db.execute(delete(LegacyEmployer).where(LegacyEmployer.id == UUID(row_id), LegacyEmployer.company_id == UUID(company)))
                else:
                    db.execute(update(LegacyEmployer).where(LegacyEmployer.id == UUID(row_id), LegacyEmployer.company_id == UUID(company)).values(name=values[0], normalized_name=values[1]))
            db.commit()
        else:
            db.rollback()


if __name__ == "__main__":
    main()
