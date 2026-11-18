# Phase 83 — Strict Batlokoa new-only client registration contract

Before a Batlokoa employee-facing registration endpoint can safely be
enabled, its accepted request shape must be explicit and lossless.

The current internal atomic writer is deliberately restricted to a minimal
client profile. It does not yet support banking, debt, address, employer,
salary, marital-status, email or password fields. The broad legacy
`AssistedCompanyClientCreate` allows those fields, but forwarding them to
the minimal writer would either fail or risk silently dropping customer
information if other callers reshape the request first.

This phase introduces a separate Pydantic
`StrictNewOnlyClientRegistration` contract that:

- Forbids extra keys, including unsupported fields, rather than ignoring
  additional bank or employment details.
- Requires branch, identity, contact, date of birth, gender, employment
  status, district and explicit boolean consent decisions.
- Requires at least one nonblank national ID or passport.
- Converts to the existing assisted DTO only via an explicit supported
  mapping and rechecks compatibility with `_minimal_only`.
- Uses automated tests to prove unsupported fields and missing mandatory
  information are refused and passport-only identities are retained.

The Phase 83 contract **does not create an API route**, does not perform
writes or deploy anything. The full form capture, loan application and loan
origination pathways must be designed and certified separately.

Production registration remains disabled. The four normalized identity
indexes still require the approved real-data audit and DBA-led rollout.
