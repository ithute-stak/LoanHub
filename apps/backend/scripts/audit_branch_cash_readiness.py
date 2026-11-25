"""Read-only, tenant-scoped cash-session / treasury opening reconciliation audit.

Does not modify, backfill or activate anything. This tool intentionally
reports mismatches for human review instead of guessing opening cash.
Usage:
  LOANHUB_CASH_AUDIT_DATABASE_URL=... python -m scripts.audit_branch_cash_readiness \
      --company-id UUID --from-date YYYY-MM-DD --to-date YYYY-MM-DD

Only company/branch UUIDs and business dates appear in output; no borrower data.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

MAX_SESSIONS = 1000

AUDIT_SQL = text("""
SELECT
    s.id::text AS session_id,
    s.branch_id::text AS branch_id,
    s.data->>'business_date' AS business_date,
    s.data->>'counted_opening' AS counted_opening,
    s.status AS session_status,
    l.id::text AS ledger_id,
    COALESCE(opening.linked_count, 0) AS linked_count,
    COALESCE(opening.linked_amount, 0) AS linked_amount,
    COALESCE(moves.posted_cash_count, 0) AS posted_cash_count
FROM company_operating_records s
LEFT JOIN branch_daily_ledgers l
  ON l.company_id = s.company_id
 AND l.branch_id = s.branch_id
 AND l.business_date::text = s.data->>'business_date'
LEFT JOIN LATERAL (
    SELECT count(*) AS linked_count, COALESCE(sum(src.amount),0) AS linked_amount
    FROM branch_opening_sources src
    WHERE src.daily_ledger_id = l.id AND src.payment_method = 'cash'
      AND src.is_confirmed = true AND src.is_voided = false
      AND src.source_reference = 'DAILY-CASH-OPEN:' || s.id::text
) opening ON true
LEFT JOIN LATERAL (
    SELECT count(*) AS posted_cash_count
    FROM treasury_entries e
    WHERE e.daily_ledger_id = l.id AND e.payment_method = 'cash'
      AND e.is_voided = false AND e.approval_status IN ('posted','approved')
) moves ON true
WHERE s.company_id = :company_id
  AND s.module = 'cash_control'
  AND s.record_type = 'daily_cash_session'
  AND s.data->>'business_date' BETWEEN :from_date AND :to_date
ORDER BY s.data->>'business_date' DESC, s.branch_id
LIMIT :limit
""")


def classify(row, *, as_of: date | None = None) -> list[str]:
    issues = []
    # An old session left open is a separate activation blocker even when
    # its counted amount and Treasury projection appear consistent.
    if as_of and row.get('session_status') == 'open':
        try:
            if date.fromisoformat(row['business_date']) < as_of:
                issues.append('STALE_OPEN_CASH_SESSION')
        except (ValueError, TypeError, KeyError):
            issues.append('INVALID_SESSION_BUSINESS_DATE')
    if row["branch_id"] is None:
        issues.append("NO_BRANCH")
    if row["ledger_id"] is None:
        issues.append("MISSING_TREASURY_DAY")
    try:
        count = Decimal(str(row["counted_opening"]))
        if not count.is_finite() or count < 0:
            issues.append("INVALID_COUNTED_OPENING")
            count = None
    except (InvalidOperation, TypeError, ValueError):
        issues.append("INVALID_COUNTED_OPENING")
        count = None
    if row["ledger_id"] is not None:
        linked = int(row["linked_count"])
        if linked == 0:
            issues.append("MISSING_SESSION_OPENING_LINK")
        elif linked != 1:
            issues.append("MULTIPLE_SESSION_OPENING_LINKS")
        elif count is not None and Decimal(str(row["linked_amount"])) != count:
            issues.append("CASH_OPENING_MISMATCH")
        if int(row["posted_cash_count"]) and not linked:
            issues.append("CASH_POSTINGS_WITHOUT_SESSION_OPENING_LINK")
    return issues


def audit(company_id: UUID, from_date: date, to_date: date, dsn: str) -> dict:
    if from_date > to_date:
        raise ValueError("from-date cannot exceed to-date")
    engine = create_engine(dsn, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text("SET TRANSACTION READ ONLY"))
                rows = conn.execute(AUDIT_SQL, {
                    "company_id": str(company_id),
                    "from_date": from_date.isoformat(),
                    "to_date": to_date.isoformat(),
                    "limit": MAX_SESSIONS + 1,
                }).mappings().all()
        if len(rows) > MAX_SESSIONS:
            return {
                "company_id": str(company_id), "ready": False, "truncated": True,
                "reason": "More than 1000 sessions; narrow date range",
            }
        summary = Counter()
        exceptions = []
        as_of = datetime.now(ZoneInfo('Africa/Maseru')).date()
        for row in rows:
            codes = classify(row, as_of=as_of)
            summary.update(codes)
            if codes:
                exceptions.append({
                    "branch_id": row["branch_id"],
                    "business_date": row["business_date"],
                    "codes": codes,
                })
        return {
            "company_id": str(company_id),
            "date_from": from_date.isoformat(), "date_to": to_date.isoformat(),
            "read_only": True, "sessions_checked": len(rows),
            "ready": bool(rows) and not exceptions,
            "issue_counts": dict(summary),
            "exceptions": exceptions[:50],
            "exceptions_omitted": max(0, len(exceptions) - 50),
            "note": (
                "No matching cash sessions is not approval to activate. "
                "A clean result is necessary but insufficient; certify transaction "
                "locks, branch scope, reconciliation and authorised activation separately."
            ),
        }
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company-id", type=UUID, required=True)
    parser.add_argument("--from-date", type=date.fromisoformat, required=True)
    parser.add_argument("--to-date", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("LOANHUB_CASH_AUDIT_DATABASE_URL")
    if not dsn:
        parser.error("Set LOANHUB_CASH_AUDIT_DATABASE_URL to an approved read-only database connection")
    report = audit(args.company_id, args.from_date, args.to_date, dsn)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
