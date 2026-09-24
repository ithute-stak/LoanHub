# Production safety entry points

For LoanHub production deployment and recovery, use these checked-in runbooks:

- `production-release-process.md` — normal forward-only release process.
- `vps-pull-latest.md` — how a generic VPS `pull loanhub latest` wrapper must delegate release selection.
- `recovery-after-stale-release.md` — recovery after a stale or migration-incompatible release attempt.
- `production-deploy-incident-2026-09-24.md` — incident record and corrective controls for the stale-release selection failure.
