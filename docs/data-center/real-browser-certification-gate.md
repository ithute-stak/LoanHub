# LoanHub Data Center — Real-browser certification gate

Status: **NOT CERTIFIED**. This plan is an evidence checklist, not proof that browser tests ran.
Reference baseline: PR #842, production image `4e0c904cf8efc4f881b91ed7c1a8111496b4bfb1` (2026-11-23).
Production Batlokoa capture must remain **disabled** until all gates below pass and an authorized owner explicitly approves a controlled pilot.

## Prerequisites
- Use two independent browser profiles (A and B), not two tabs sharing a login.
- Use an isolated test company and synthetic clients; never create or mutate real loans, receipts, balances or staff credentials.
- Record browser versions, environment, tenant/company IDs (non-sensitive identifiers only), build SHA, wall clock and test operator.
- Confirm capture feature switch is disabled for real production companies before and after testing.
- Export sanitized HAR/network traces, browser console, relevant server correlation IDs and journal cursor ranges. **Never** store tokens, passwords, national IDs, or customer data in test artifacts.
- If a test cannot be run safely outside production, mark BLOCKED; do not substitute a simulated pass.

## Case matrix (each requires evidence and a PASS/FAIL/BLOCKED verdict)

| ID | Scenario | Expected result |
|---|---|---|
| RB-01 | A and B sign in to the same synthetic company; A makes an authorized test-only change | B receives exactly one valid updated projection (or replay resolves it); no stale view after refresh |
| RB-02 | Disconnect B network, make two ordered test-only changes in A, reconnect B | Replay includes every missed authorized event in cursor order; no duplicates or gaps |
| RB-03 | Force WebSocket disconnect/reconnect and reload B mid-replay | B recovers to the same final state as a fresh authenticated read |
| RB-04 | B logs out with cached Data Center state visible | Cached sensitive projection cleared; unauthenticated replay and socket fail closed |
| RB-05 | B switches from company X to Y (where authorized) | X's projection, cursors, journal, listeners and pending requests do not surface in Y |
| RB-06 | Use two accounts from different companies; attempt cross-company replay | No company X data exposed to Y; server rejects mismatched scope |
| RB-07 | Replace/expire access token during replay | Prior-session listeners and cached data cleared; old token cannot replay |
| RB-08 | Revoke/deactivate user/staff/company during active test session | Server rejects further replay; browser clears/invalidates state |
| RB-09 | Introduce duplicate cursor, stale generation, malformed event envelope, skipped page | Client rejects invalid stream and resynchronizes safely or fails closed; never silently accepts corruption |
| RB-10 | Overlapping page boundaries/high event volume within a synthetic dataset | Cursor monotonicity and max page constraints hold; final projection consistent |
| RB-11 | Close browser, reopen and sign in as different test user | No previous user's data appears even transiently |
| RB-12 | Compare UI and authorized API after reconnect for test event IDs | Matching final business state, no double application |

## Evidence record
For each case record: test ID; UTC start/end; environment and exact release SHA; tester; company/account pseudonyms; reproducible steps; relevant event IDs/cursor/generation; network and console observations; PASS/FAIL/BLOCKED; issue URL for failures. Screenshot or record only synthetic data.

## Release gate
1. All RB-01 through RB-12 PASS with auditable synthetic-data evidence.
2. Automated CI replay tests still PASS on the exact candidate SHA; no unreviewed code changes.
3. Independent security review confirms company isolation, token revocation, websocket authorization, cache lifecycle and no leak of customer data.
4. Pilot owner signs off, explicitly names test company, start/end window, monitoring owner and rollback method.
5. Enable capture for **only** the signed-off isolated company through an audited feature flag; leave Batlokoa production companies disabled.
6. Monitor failed replay, gaps/duplicates, reconnect success, stale view age, authorization failures, server errors and resource usage. Define numeric SLO thresholds from observed baseline **before** pilot.
7. Abort on any cross-tenant leak, wrong balance, duplicate business event, missed event without recovery, invalid authorization or unexplained inconsistency. Disable pilot flag, preserve sanitized evidence, and revert release only if required under the existing rollback procedure.

**No global enablement or production-company activation is authorized by this document.**
