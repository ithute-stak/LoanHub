# Security, Audit, Error and File Design

## Tenancy

Every company operation resolves an authenticated membership and selected `X-Company-ID`. Non-management staff become branch-scoped when a branch is assigned. IDs supplied by the browser are never trusted without database membership checks.

## Error handling

Unhandled errors receive a request ID and fingerprint. Ordinary users receive a generic safe response. The system stores the diagnostic event and only active platform owners receive the technical notification. Repeated fingerprints are grouped and rate-limited to prevent spam.

## Audit

Normal ORM create/update/delete operations and sensitive explicit workflows record actor, company, branch, entity, request ID and changed fields. Presence-only `last_seen_at` updates are excluded from actionable CRUD notifications.

## Chat

The browser uses one shared realtime socket per tab. A short-lived HttpOnly WebSocket-session cookie authenticates the socket without placing the main access token in the URL. Redis distributes events across workers.

## Managed files

Uploads validate extension, MIME, size, visibility and context; compute SHA-256; use atomic writes; and can encrypt content at rest. Downloads re-check tenant, branch, owner or conversation membership. Voice notes and generated reports use the same storage layer.

## Encryption statement

The v1.0 design provides HTTPS/WSS in transit and AES-GCM-style server-managed encryption at rest for chat/file content. It is not client-to-client end-to-end encryption because the authorised server must enforce permissions and deliver content.
