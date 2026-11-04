# Wacom workstation enrollment and challenge persistence

This phase adds tenant-scoped PostgreSQL tables and a DB-level atomic
consume primitive for Ed25519 workstation proof-of-possession. It does
not create an enrollment API or activate capture.

## Tables

`wacom_workstation_enrollments` stores company ID, operator ID,
workstation UUID, a **public** Ed25519 key, status
(`pending`, `active`, `revoked`), approval and revocation times.
No private key is stored in LoanHub.

`wacom_workstation_challenges` stores company, enrollment and
candidate signing-session identifiers, a unique random 32-byte nonce,
expiration and consumed timestamp. A nonce is not authentication by
itself.

The migration has foreign keys, tenant indexes, unique enrollment
(company/workstation), unique nonce and database checks for public-key
and nonce lengths.

The new service `consume_verified_wacom_challenge` uses one
conditional PostgreSQL `UPDATE ... RETURNING` and requires a matching
tenant/enrollment/session, unused, unexpired challenge and an active,
approved, unrevoked enrollment. A valid signature, current document
hash and authenticated operator/session authority must be verified
**before** calling it. The caller must commit the transaction before
granting any temporary preview authority.

## Required before activation

- Privileged, audited device registration and dual-control approval
- Proof-of-possession challenge issuance under the authenticated tenant
- Server-side verification using the stored enrolled public key
- A PostgreSQL integration test for concurrent consumption and tenant
  restrictions (the initial tests check SQL construction)
- Key rotation, device loss response and enrollment revocation
- Secure backend-to-local connector communication and capture expiry
- Borrower identity, consent, encrypted evidence and PDF signature flow

Deploy migration only as part of reviewed schema rollout with backup
and downgrade assessment. No new HTTP route, signing action, or
production deployment is included in this PR.
