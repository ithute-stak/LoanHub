# Chat and File Security

## Chat design

- Direct and group conversations are persisted in PostgreSQL.
- The directory is filtered according to user role, tenant relationship and loan relationship.
- Conversation membership is checked on every message and attachment operation.
- Realtime delivery uses authenticated WebSocket user channels.
- Polling provides a fallback when the socket reconnects.
- Messages have stable client IDs to reduce duplicate sends.
- Edit and delete events are propagated to connected participants.
- Read positions produce unread counts.

## What is deliberately not claimed

- No Meta WhatsApp connection is included.
- No phone-address-book synchronisation is included.
- No end-to-end encryption is included.
- No disappearing-message or voice/video calling implementation is included.

## Managed-file visibility

| Visibility | Access rule |
|---|---|
| private | uploader/owner only |
| conversation | active participants in the linked conversation |
| branch | branch members; company management may oversee |
| company | active members of the same company tenant |
| confidential | authorised company management and platform administration |
| platform | platform administration |

## Supported content

The interface accepts PDFs, images and common office documents, subject to backend size and content-type limits. The system stores the original filename, safe storage key, MIME type, size, uploader, scope, visibility and deletion state.

## Production recommendations

- Use object storage rather than local disk for multi-server deployments.
- Scan uploads for malware.
- Reject executable and dangerous archive formats.
- Inspect file signatures instead of trusting only browser MIME types.
- Use encrypted storage and TLS.
- Retain access/download audit records.
- Define deletion, retention and regulatory policies.
- Use signed links that expire.
- Set per-tenant storage quotas.
