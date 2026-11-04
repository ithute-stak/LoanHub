# Wacom temporary preview admission — backend gate

The physical STU-540 calibrated local test succeeded (206 SDK reports,
50 contact points, two assembled strokes). The Go connector and browser
canvas are still **not linked through authenticated transport**.

The new pure backend admission policy checks an existing persisted
`ContractPadSigningSession` against:
- Authenticated operator and company identity
- Current contract ID and canonical 64-digit SHA-256 contract hash
- Exact session UUID, active status and timezone-aware expiration
- No already captured evidence, cancellation or completion

**Important:** Caller must retrieve the authorized, tenant-scoped session
and current contract from the database and must not accept session
identity, borrower identity, company identity or contract hash as
self-attested browser proof. This policy is not an API endpoint and
does not mint a token, establish identity, authorize a real signature,
stream pen data, or finalize a document.

Integration steps still required:
1. Authenticated backend endpoint retrieves and locks the active session,
   verifies borrower/tenant, RBAC, contract version and revocation.
2. Backend issues a single-use, short-lived, audience-bound preview ticket
   only to an authenticated workstation using a secured channel.
3. Connector validates the backend-issued ticket and local device capture,
   applying bounds/rate limits and cancellation before streaming points.
4. UI renders via the guarded preview component; no preview can be
   submitted as legal signing evidence.
5. Separately implement verified borrower identity, per-contract consent,
   secure evidence persistence, audit and signed PDF finalization.

Existing email OTP signing remains unchanged.
