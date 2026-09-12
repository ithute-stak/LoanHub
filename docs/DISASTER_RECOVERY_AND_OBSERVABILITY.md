# Disaster recovery, observability and SRE controls

LoanHub exposes `/health/live`, `/health/ready` and Prometheus-compatible `/metrics`. Requests receive `X-Request-ID`; API request logs are structured JSON and include request ID, method, route, status and latency without logging request bodies or access tokens. Redis is treated as a resilience dependency: readiness reports it as degraded when unavailable while the application keeps operating using bounded in-process fallbacks for controls that support them. PostgreSQL remains a hard readiness dependency.

Recommended serious-SME production objectives are **RPO <= 15 minutes** and **RTO <= 60 minutes** for the core loan ledger and borrower operations. These are operating targets, not guarantees. The lender should measure achieved recovery during drills and tighten infrastructure until the targets are repeatedly met.

## Backup and restore

`scripts/backup_postgres.sh` creates a compressed PostgreSQL custom-format backup, writes a SHA-256 checksum, uses restrictive file permissions and applies retention. `scripts/restore_postgres.sh` verifies the checksum before restore. `scripts/drill_backup_restore.sh` performs an isolated restore and verifies that the restored Alembic revision matches the source database. CI runs this drill on every release candidate.

Production backups should be automated at least every 15 minutes using WAL/PITR or a managed PostgreSQL service in addition to scheduled logical backups. Store copies in a separate failure domain, encrypt them at rest and in transit, restrict deletion rights, and test a representative restore at least monthly. A successful backup job is not recovery evidence; a successful restore drill is.

## Alerting baseline

Alert when the API readiness endpoint is unavailable for more than 2 minutes, PostgreSQL connections fail, HTTP 5xx exceeds 2% over 5 minutes, p95 API latency exceeds the lender-approved threshold for 10 minutes, disk/object-storage capacity is near exhaustion, backup age exceeds the RPO, a restore drill fails, malware scanning is unavailable in fail-closed production mode, or Redis remains degraded long enough to affect realtime/cache workloads.

Prometheus/Grafana, a managed monitoring service, or another compatible system can consume `/metrics`. Sentry integration is enabled by setting `SENTRY_DSN`; production should keep PII collection disabled and choose a controlled traces sample rate. Alert ownership, escalation contacts and runbooks must be configured outside source control.

## Recovery sequence

Declare the incident and freeze risky writes if ledger integrity is uncertain. Preserve evidence and identify the last known-good recovery point. Restore PostgreSQL into an isolated environment, verify the checksum, Alembic head and accounting integrity checker, verify object-storage availability/checksums, then run authenticated smoke tests before switching traffic. Record actual RPO/RTO, data loss if any, cause, remediation and follow-up controls.
