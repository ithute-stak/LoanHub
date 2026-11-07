# LoanHub / IthutePay — Phase 35 future financial-engine reference

This directory preserves the proposed **offline, non-executing financial
domain code** from the Phase 35 development package as reviewable source.
It is **not** installed under `apps/backend`, not imported by the running
service, not an Alembic revision, not a provider adapter and not a release
configuration. Nothing here enables payments.

The Phase 31 preview route and its tests already merged in LoanHub PR #610;
the fingerprint guard merged separately in PR #611. They are intentionally
not duplicated here. The original Phase 35 offline ZIP also contained an
application-staging script, whose purpose is obsolete after PR #610 and is
not installed as runtime code.

## Source map

- financial_allocation.py: pure allocation proposals
- double_entry.py: pure balanced journal proposals
- payment_lifecycle.py: fail-closed lifecycle transition reducer
- provider_evidence.py: test-only HMAC callback boundary
- reconciliation.py: pure settlement matching
- idempotency_contract.py: duplicate-key classification
- postgres_reservation.py: **unapproved** PostgreSQL sketch
- 01_collection_intent_reservation.sql: **unapproved** schema sketch
- 02_reservation_rls_draft.sql: **comment-only** RLS sketch
- test_*.py: isolated regression tests; not live provider tests

Run manually from this directory using:
```bash
python3 -m unittest discover -s . -p 'test_payment_lifecycle.py' -v
python3 -m unittest discover -s . -p 'test_financial_engine.py' -v
python3 -m pytest -q test_postgres_reservation.py
```

Those tests do not replace real database concurrency, RLS, lender policy,
provider callback, ledger, reconciliation and failure-injection testing.

The production collection-preview flags remain disabled by default. Never
enable actual collection, payout, fee posting, shared custody or shortcode
changes from this directory. Release and migrations require separate approval.
