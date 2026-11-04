# Wacom — operator-authenticated workstation challenge API

This phase makes the previously isolated Ed25519 workstation proof
usable through two real, tenant-scoped LoanHub FastAPI endpoints.

- POST `/api/v1/contract-signing/contracts/{contract_id}/pad/sessions/{session_id}/workstation-challenges`
  accepts `{"workstation_id": "<enrolled UUID>"}` and creates a
  random 32-byte, one-use PostgreSQL challenge expiring after 30s.
- POST `/api/v1/contract-signing/contracts/{contract_id}/pad/sessions/{session_id}/workstation-proofs`
  accepts challenge UUID, workstation UUID and Base64 Ed25519 signature,
  checks it against the enrolled workstation public key, and atomically
  consumes the challenge with `UPDATE ... RETURNING`.

Both endpoints use existing authenticated operator authorization,
tenant/branch-scoped contract access, and a pad session owned by the
same operator. The contract must still pass current preview eligibility,
including its hash, expiry and unsigned status. Enrollment must be
active, approved, unrevoked and assigned to this company and operator.

Challenge issuance is bounded to three outstanding unused challenges
per enrolled workstation/session; this is an application-level limit
and is not a replacement for ingress/IP/device rate limiting and
concurrency-safe quotas.

Responses set `Cache-Control: no-store`. Proof success explicitly
returns `capture_enabled: false`, `preview_ticket_issued: false`
and `contract_signed: false`. No borrower data, pen coordinates,
images, signed contracts or private workstation keys are returned.

**Still missing before physical browser capture:**
- An audited, privileged enrollment and approval/rotation workflow;
  no public enrollment endpoint exists in this PR.
- Controlled workstation private-key provisioning and a transport to
  deliver/answer the challenge without sending secrets to a browser.
- Backend issuance of short-lived preview tickets after verification,
  integrated session revocation, and the authenticated Go local endpoint.
- Safe physical pen source and contract/session-bound browser transport.
- Full PostgreSQL concurrency, load, CSRF/origin, cancellation and
  physical-device integration testing.

Run in isolated staging first; no automatic VPS cutover or signing
activation is included. Existing email OTP is unaffected.
