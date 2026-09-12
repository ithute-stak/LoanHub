# LoanHub Corrected Backend Release

This release focuses on backend correctness and recoverable deployment rather than adding new product features.

## Included

- Linear, recoverable Alembic history
- Permanent compatibility for the recorded `3957062b7c66` revision
- Canonical final migration head `d4e7b6c1a930`
- Correct chat/audit model mapping
- Hardened global audit hooks
- Restored selected-offer foreign key
- Normalized index names
- Safe company-staff foreign-key migration
- Offline-safe historical migrations
- Complete environment template
- Migration and route validation scripts
- Secret-free and cache-free release packaging

## Before production

1. Restore your own `.env` and JWT keys securely.
2. Back up PostgreSQL.
3. Stop the API and maintenance worker.
4. Run `./scripts/migrate_safely.sh` against staging.
5. Run critical API workflow tests against staging.
6. Deploy only after the staging database reaches `d4e7b6c1a930` successfully.
