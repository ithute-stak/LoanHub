# Wacom — tenant-scoped workstation registration and approval

This phase adds three real authenticated FastAPI operations under
`/api/v1/contract-signing/workstations`:

- `POST /`: an authorized lending operator registers a workstation UUID
  and its **public** Ed25519 key; new enrollment is **pending**, not trusted.
- `POST /{enrollment_id}/approve`: a company owner/admin who is
  **different from the registering operator** approves a pending enrollment.
- `POST /{enrollment_id}/revoke`: a company owner/admin permanently revokes
  a pending or active enrollment, disabling subsequent workstation proof
  challenges because challenge APIs require active, unrevoked enrollment.

All routes rely on the existing tenant-authenticated role context and
enforce company scope on enrollment access. Keys must be canonical Base64
of exactly 32 bytes. Private keys must **never** be uploaded. Responses
carry no key material, are no-store and explicitly leave capture disabled.

The existing `workstation-challenges` and `workstation-proofs` routes
in PR #574 can now be used with separately approved enrollment records,
but *authentication still is not signing authorization*.

Important remaining limitations:
- Workstation secure key creation/provisioning, origin and CSRF protections,
  approval audit review, enrollment rotation/replacement, and global rate
  limits need an end-to-end security assessment.
- An operator with an approved enrollment still needs a verified physical
  workstation proof and session-scoped, single-use preview ticket before
  any SDK access.
- Physical pen capture streaming to the browser, consent, identity verification
  and legally effective PDF signatures remain disabled.
- Test on an isolated staging database before production exposure.
