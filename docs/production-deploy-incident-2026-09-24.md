# Production deploy incident — 2026-09-24

## Summary

The VPS-side `latest` selector chose release `28b2e74235d227c9e7352eb9ae12da90adfa5162` while the production/current code marker was `d97ef70a456b102b7d7d895618506c8e957d224e`.

Git history shows `28b2e74235d227c9e7352eb9ae12da90adfa5162` is an ancestor of `d97ef70a456b102b7d7d895618506c8e957d224e`, not a forward release. The selected image predates Alembic revision `e9x3y5z7a250`, while the live database had already recorded that revision. Alembic therefore correctly refused to migrate with `Can't locate revision identified by 'e9x3y5z7a250'`.

## Root cause

The release-selection path treated the newest discoverable/published image as deployable without proving that it was a forward descendant of the currently deployed release. A successful historical release image is not automatically a valid production upgrade.

## Corrective controls

The checked-in production deployment helper now:

- treats normal deployment as forward-only and verifies GitHub commit ancestry;
- resolves `latest` only from successful `LoanHub Release Images` runs that are forward descendants of the current production SHA;
- confirms both immutable GHCR images exist before selecting a release;
- compares the live `alembic_version` revision(s) with the candidate backend image before taking a backup or attempting migrations;
- propagates the real migration container exit code using `docker compose run --rm --no-deps migrate`;
- does not replace backend/frontend containers when migration compatibility or migration execution fails;
- starts application services without re-running the Compose migration dependency after a successful migration;
- has CI/static safety checks protecting these deployment properties.

## Recovery rule

Do not edit `alembic_version` and do not stamp the database backward to make an older image run. Recover the existing/current release first, then deploy only a tested forward release.
