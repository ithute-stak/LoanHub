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
    COALESCE(moves.posted_cash_count, 0) AS posted_cash_count,
    COALESCE(moves.treasury_cash_net, 0) AS treasury_cash_net,
    COALESCE(journal.posted_journal_cash_count, 0) AS posted_journal_cash_count,
    COALESCE(journal.posted_journal_cash_net, 0) AS posted_journal_cash_net
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
    SELECT count(*) AS posted_cash_count,
           COALESCE(sum(CASE WHEN e.direction = 'money_in' THEN e.amount ELSE -e.amount END), 0)
              AS treasury_cash_net
    FROM treasury_entries e
    WHERE e.daily_ledger_id = l.id AND e.payment_method = 'cash'
      AND e.is_voided = false AND e.approval_status IN ('posted','approved')
) moves ON true
LEFT JOIN LATERAL (
    SELECT count(*) AS posted_journal_cash_count,
           COALESCE(sum(jl.debit - jl.credit), 0) AS posted_journal_cash_net
    FROM journal_entries je
    JOIN journal_lines jl ON jl.journal_entry_id = je.id
    JOIN accounting_accounts aa ON aa.id = jl.account_id AND aa.code = '1000'
    WHERE je.company_id = s.company_id AND je.branch_id = s.branch_id
      AND je.entry_date::text = s.data->>'business_date'
      AND je.status = 'posted'
      AND je.posted_at >= NULLIF(s.data->>'opened_at','')::timestamptz
) journal ON true
WHERE s.company_id = :company_id
  AND s.module = 'cash_control'
  AND s.record_type = 'daily_cash_session'
  AND s.data->>'business_date' BETWEEN :from_date AND :to_date
ORDER BY s.data->>'business_date' DESC, s.branch_id
LIMIT :limit
""")


# The requested date window must not be allowed to hide an older open
# session elsewhere in the company. Activation is company-scoped and needs
# a company-wide check of every open session outside today, including
# malformed and future-dated values, not only the displayed audit range.
STALE_SESSIONS_SQL = text("""
SELECT count(*) FROM company_operating_records
WHERE company_id = :company_id
  AND module = 'cash_control'
  AND record_type = 'daily_cash_session'
  AND status = 'open'
  AND (
      data->>'business_date' IS NULL
      OR data->>'business_date' <> :as_of
  )
""")


def classify(row, *, as_of: date | None = None) -> list[str]:
    issues = []
    # An old session left open is a separate activation blocker even when
    # its counted amount and Treasury projection appear consistent.
    if as_of and row.get('session_status') == 'open':
        try:
            business_date = date.fromisoformat(row['business_date'])
            if business_date < as_of:
                issues.append('STALE_OPEN_CASH_SESSION')
            elif business_date > as_of:
                issues.append('FUTURE_OPEN_CASH_SESSION')
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
        # Treasury is an operational projection, not the physical count.
        # Compare journal net and treasury net without treating one as a
        # replacement for the other. Both missing and surplus projections
        # require review before financial controls are activated.
        if ("posted_journal_cash_net" in row and "treasury_cash_net" in row
                and Decimal(str(row["posted_journal_cash_net"]))
                != Decimal(str(row["treasury_cash_net"]))):
            issues.append("CASH_JOURNAL_TREASURY_MISMATCH")
    return issues


def audit(company_id: UUID, from_date: date, to_date: date, dsn: str) -> dict:
    if from_date > to_date:
        raise ValueError("from-date cannot exceed to-date")
    as_of = datetime.now(ZoneInfo('Africa/Maseru')).date()
    engine = create_engine(dsn, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text("SET TRANSACTION READ ONLY"))
                stale_open_sessions = int(conn.execute(STALE_SESSIONS_SQL, {
                    "company_id": str(company_id),
                    "as_of": as_of.isoformat(),
                }).scalar_one())
                rows = conn.execute(AUDIT_SQL, {
                    "company_id": str(company_id),
                    "from_date": from_date.isoformat(),
                    "to_date": to_date.isoformat(),
                    "limit": MAX_SESSIONS + 1,
                }).mappings().all()
        if len(rows) > MAX_SESSIONS:
            return {
                "company_id": str(company_id), "ready": False, "truncated": True,
                "company_wide_stale_open_sessions": stale_open_sessions,
                "reason": "More than 1000 sessions; narrow date range",
            }
        summary = Counter()
        exceptions = []
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
            "company_wide_stale_open_sessions": stale_open_sessions,
            "ready": bool(rows) and not exceptions and stale_open_sessions == 0,
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
