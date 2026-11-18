"""Read-only global aggregate cross-source identity/legacy collision audit.

No matched identifiers, borrowers, accounts or loan balances are returned.
This is a conservative review signal, not a deduplication recommendation.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


class LegacyIdentityAuditUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class LegacyIdentityCrossReference:
    national_id_overlap_groups: int
    passport_overlap_groups: int
    repeated_legacy_passport_groups: int
    requires_historical_review: bool


# Constant, reviewed SQL: SELECT only aggregates, no tenant scope. Each
# legacy capture may represent a legitimate independent loan or installment.
_SQL = {
    "national_id_overlap_groups": """
        SELECT count(*) FROM (
          SELECT DISTINCT lower(btrim(lc.national_id)) AS key
          FROM legacy_loan_captures lc
          JOIN people p ON lower(btrim(p.national_id)) = lower(btrim(lc.national_id))
          WHERE lc.national_id IS NOT NULL AND btrim(lc.national_id) <> ''
            AND p.national_id IS NOT NULL AND btrim(p.national_id) <> ''
        ) overlaps
    """,
    "passport_overlap_groups": """
        SELECT count(*) FROM (
          SELECT DISTINCT lower(btrim(lc.passport_number)) AS key
          FROM legacy_loan_captures lc
          JOIN people p ON lower(btrim(p.passport_number)) = lower(btrim(lc.passport_number))
          WHERE lc.passport_number IS NOT NULL AND btrim(lc.passport_number) <> ''
            AND p.passport_number IS NOT NULL AND btrim(p.passport_number) <> ''
        ) overlaps
    """,
    "repeated_legacy_passport_groups": """
        SELECT count(*) FROM (
          SELECT lower(btrim(passport_number))
          FROM legacy_loan_captures
          WHERE passport_number IS NOT NULL AND btrim(passport_number) <> ''
          GROUP BY lower(btrim(passport_number))
          HAVING count(*) > 1
        ) repeated
    """,
}


def inspect_legacy_identity_cross_reference(db: Session) -> LegacyIdentityCrossReference:
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        raise LegacyIdentityAuditUnavailable("PostgreSQL required")
    if not db.in_transaction():
        raise LegacyIdentityAuditUnavailable("Caller-owned read-only transaction required")
    if db.execute(text(
        "SELECT current_setting('transaction_read_only')"
    )).scalar_one() != "on":
        raise LegacyIdentityAuditUnavailable("Read-only transaction required")
    counts = {}
    for name, sql in _SQL.items():
        result = db.execute(text(sql)).scalar_one()
        if type(result) is not int or result < 0:
            raise LegacyIdentityAuditUnavailable("Untrustworthy aggregate result")
        counts[name] = result
    return LegacyIdentityCrossReference(
        **counts, requires_historical_review=any(counts.values()))
