"""Aggregate-only historical borrower-link triage for release reviewers.

This deliberately returns no identity strings, record IDs or company IDs,
and never guesses or mutates a missing borrower_id. A matched National ID
alone is not authorization to repair financial history.
"""
from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy import text
from sqlalchemy.orm import Session


class LegacyLinkTriageUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class LegacyLinkTriage:
    matching_identity_groups: int
    linked_only_groups: int
    mixed_linkage_groups: int
    unlinked_only_groups: int
    unlinked_legacy_rows: int
    unlinked_with_single_borrower_and_company_account: int
    unlinked_needing_manual_review: int
    registration_enabled: bool = False
    automatic_repairs_allowed: bool = False


_SQL = """
WITH matching_rows AS (
    SELECT l.id AS legacy_id, l.borrower_id, l.company_id,
           lower(btrim(l.national_id)) AS identity_key, p.user_id,
           b.id AS existing_link, b.user_id AS existing_user_id
    FROM legacy_loan_captures l
    JOIN people p
      ON lower(btrim(p.national_id)) = lower(btrim(l.national_id))
    LEFT JOIN borrowers b ON b.id = l.borrower_id
    WHERE l.national_id IS NOT NULL AND btrim(l.national_id) <> ''
      AND p.national_id IS NOT NULL AND btrim(p.national_id) <> ''
),
groups AS (
    SELECT identity_key,
           bool_or(existing_link IS NOT NULL AND existing_user_id = user_id) AS linked,
           bool_or(existing_link IS NULL OR existing_user_id <> user_id) AS unlinked
    FROM matching_rows GROUP BY identity_key
),
unlinked_rows AS (
    SELECT DISTINCT legacy_id, company_id, user_id
    FROM matching_rows
    WHERE borrower_id IS NULL
),
candidate_counts AS (
    SELECT u.legacy_id,
      (SELECT count(*) FROM borrowers b
       WHERE b.user_id = u.user_id) AS borrower_count,
      (SELECT count(*) FROM company_borrower_accounts a
       JOIN borrowers b ON b.id = a.borrower_id
       WHERE b.user_id = u.user_id AND a.company_id = u.company_id
      ) AS same_company_accounts
    FROM unlinked_rows u
)
SELECT
  (SELECT count(*) FROM groups),
  (SELECT count(*) FROM groups WHERE linked AND NOT unlinked),
  (SELECT count(*) FROM groups WHERE linked AND unlinked),
  (SELECT count(*) FROM groups WHERE NOT linked AND unlinked),
  (SELECT count(*) FROM unlinked_rows),
  (SELECT count(*) FROM candidate_counts
    WHERE borrower_count = 1 AND same_company_accounts > 0)
"""


def inspect_legacy_link_triage(db: Session) -> LegacyLinkTriage:
    """Inspect only within a caller-owned, actually read-only PostgreSQL transaction."""
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        raise LegacyLinkTriageUnavailable("PostgreSQL required")
    if not db.in_transaction():
        raise LegacyLinkTriageUnavailable("Read-only transaction required")
    if db.execute(text("SELECT current_setting('transaction_read_only')")).scalar_one() != "on":
        raise LegacyLinkTriageUnavailable("Read-only transaction required")
    values = tuple(db.execute(text(_SQL)).one())
    if len(values) != 6 or any(type(v) is not int or v < 0 for v in values):
        raise LegacyLinkTriageUnavailable("Unreliable aggregate linkage result")
    total, linked, mixed, unlinked, rows, candidates = values
    if linked + mixed + unlinked != total or candidates > rows:
        raise LegacyLinkTriageUnavailable("Inconsistent aggregate linkage counts")
    return LegacyLinkTriage(
        matching_identity_groups=total,
        linked_only_groups=linked,
        mixed_linkage_groups=mixed,
        unlinked_only_groups=unlinked,
        unlinked_legacy_rows=rows,
        unlinked_with_single_borrower_and_company_account=candidates,
        unlinked_needing_manual_review=mixed + unlinked,
    )
