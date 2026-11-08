-- STAGING ONLY. Execute using the approved read-only staging DB account.
-- Check only aggregate revocation state. Do not export tokens, personal records,
-- signatures, borrower data, or workstation key material.
SELECT COUNT(*) AS active_not_expired_sessions
FROM wacom_bridge_sessions
WHERE revoked_at IS NULL AND expires_at > now();

SELECT COUNT(*) AS overdue_unrevoked_sessions
FROM wacom_bridge_sessions
WHERE revoked_at IS NULL AND expires_at <= now();

SELECT COUNT(*) AS revoked_sessions
FROM wacom_bridge_sessions
WHERE revoked_at IS NOT NULL;
