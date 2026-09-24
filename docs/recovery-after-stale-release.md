# Recovery after a stale-release deployment attempt

If a stale LoanHub image is rejected because its Alembic history cannot resolve the live database revision, do not modify `alembic_version` and do not stamp the database backward.

Use the release already recorded in `/opt/loanhub/releases/current.sha` to restore/reconcile the running application:

```bash
cd /opt/loanhub
current="$(tr -d '\r\n ' < releases/current.sha)"
sudo ./scripts/deploy-production-manual.sh "$current"
```

After production is healthy again, deploy only a tested forward release:

```bash
sudo ./scripts/deploy-production-manual.sh latest
```

The deployment helper will refuse stale, behind, diverged, or migration-incompatible releases.
