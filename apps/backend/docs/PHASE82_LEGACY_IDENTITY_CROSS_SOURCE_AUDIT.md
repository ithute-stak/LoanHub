# Phase 82 — Historical passport and national-ID overlap report

The Phase 80 safety fix blocks passport matches against historical captures
globally. This phase makes those collisions visible to approved database
operators in **aggregate form only** before normalized uniqueness changes.

A dedicated read-only PostgreSQL query returns three counts:

- Distinct normalized national IDs occurring in both `people` and
  `legacy_loan_captures`.
- Distinct normalized passports occurring in both sources.
- Groups of historical captures sharing the same normalized passport.

These are **review signals**, not evidence that different historical loan
entries should be merged, deleted or settled. The SQL returns only counts and
never returns national IDs, passport values or borrower account details.

The read-only migration approval report now includes
`legacy_cross_source_counts` and
`legacy_cross_source_audit_complete`. Missing scans or any nonzero historical
intersection prevent the report from marking an operator-review candidate.
Every report continues to hardcode `safe_to_execute=false`,
`production_approved=false` and `registration_enabled=false`.

GitHub CI runs this exact service against an isolated PostgreSQL database,
using synthetic data to prove normalized comparison, aggregation and
read-only-session rejection. No production migrations, registration endpoints,
historical financial data changes, or identity matching for end users.
