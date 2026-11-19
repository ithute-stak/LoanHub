# Principal x% offline fast-track

This branch is intentionally separate from PR #766. Work here without waiting for full CI after every small change; merge into the existing feature branch only after review.

## Local workflow (Ubuntu)

```bash
git fetch origin
git switch feat/principal-x-offline-fasttrack-20261119
# Activate an already configured backend virtual environment.
bash apps/backend/scripts/principal_x_offline_check.sh
```

The runner uses the existing Python environment and executes no package installs, database connections, Alembic upgrades, network calls or Git pushes. It performs compilation, read-only migration-graph checks, focused Principal x tests, and a calculator-diff guard.

## Boundaries

- Never modify LoanHub Calculator formulas or approved repayment schedules.
- Never enable live Principal x collections until ledger, tenant, lifetime-cap, concurrency and reversal protections are validated in integration tests.
- New loans require explicit opt-in; legacy loans retain the existing model.
- The 2× original-principal lifetime ceiling is a product rule, not a statutory assertion.
- Offline checks are a developer feedback loop, **not** a release gate.

## Later integration

1. Rebase or merge this branch into `feat/principal-x-settlement-engine-20261118` after review.
2. Run complete GitHub CI on the integrated branch, including PostgreSQL migration rehearsal.
3. Merge PR #766 only when required checks pass and deployment is separately approved.

No production migration or VPS execution is part of this workflow.
