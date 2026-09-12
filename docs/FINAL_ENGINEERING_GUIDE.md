# LoanHub Final Engineering Guide

## Runtime architecture

Caddy terminates HTTPS and sends `/api/*`, `/health` and WebSocket upgrade traffic to FastAPI. Other routes go to the standalone Next.js application. PostgreSQL is the durable source of truth. Redis distributes notifications, chat and presence across API workers. The maintenance process runs lifecycle reconciliation continuously and performs the local-midnight reporting cycle in `Africa/Maseru`.

## Error visibility

- 4xx validation and permission errors are shown as safe, readable user messages.
- Unhandled 5xx errors are persisted in `system_error_logs` and grouped by fingerprint.
- Only active `superadmin` accounts receive technical incident notifications.
- Ordinary users receive a generic response with `request_id`.
- Repeated fingerprints are rate-limited to prevent notification spam.

## Role switching

Platform owners can start a time-limited impersonation session from the navigation bar. The session:

- requires a reason;
- is restricted to an active user and valid company membership;
- cannot impersonate another platform owner;
- is recorded in the audit trail;
- displays a permanent amber warning banner;
- automatically returns to the preserved platform-owner session when the token expires or a 401 is received.

Role switching is for support and workflow testing. It must never be used to conceal the actor behind a financial or administrative action.

## Chat security and files

Text bodies and file bytes are encrypted at rest with separate keys. AES-GCM provides confidentiality and tamper detection. File downloads are authorised on every request, streamed with a safe filename and checked against metadata. Uploaded content is checked using extension, declared MIME and detected signature rules. Executables and suspicious mismatches are blocked or quarantined.

Presence is based on authenticated WebSocket connections and `last_seen_at`. Voice notes use the browser microphone and are stored as managed audio files. HTTPS/WSS is mandatory in production.

## Midnight processing

At 00:00 local Lesotho time, one worker obtains a PostgreSQL advisory lock and generates idempotent PDF and CSV reconciliation reports for:

- the complete platform;
- every active company;
- every active branch.

Daily reports cover the previous day. Monday additionally produces the previous completed week. The first day of a month produces the previous month. January 1 produces the previous calendar year. Reports are stored in managed media and exposed through authorised report/file-centre downloads.

## Database alignment

The final migration `f1a9c4e7b620` follows the repaired linear history. Release validation checks one Alembic head, SQLAlchemy mapper configuration, audit-column collisions, dependency sorting, router registration, duplicate routes and OpenAPI operation IDs. Offline upgrade and downgrade SQL are generated in CI.

A live `alembic check` still requires the target PostgreSQL database and should be run on staging after migration.
