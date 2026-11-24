# Phase 90 — Authenticated Batlokoa new-client availability endpoint

This phase registers a **GET-only** endpoint:

`GET /api/v1/batlokoa/registration/availability`

The endpoint uses LoanHub's existing authenticated tenant context dependency
and also checks real active lending staff, matching user and company scope,
and an assigned branch for non-management lending roles.

The response always says **new-only registration unavailable** and explains
that independent release approval and identity-index migration approval
remain required. It never includes borrower PII, client records, identity
collision details, internal business approvals or SQL implementation details.

The endpoint has no request body, does not invoke
`create_full_new_client_atomically`, has no database write path, and
cannot be used as an enrollment feature flag. It only helps the Batlokoa
employee interface distinguish a staff-permission error from a
not-yet-released new-only registration workflow.

IMPORTANT: This endpoint does not replace or disable existing
`company-clients` assisted registration endpoints, which have separate
legacy behavior and must be audited independently before any claim that
*all* LoanHub client registration is disabled. This status refers only to
the new protected **new-only** registration path.

Future write routes must require fresh persisted staff, branch, identity,
index and full-transaction authorization. No production migration or live
new-only registration feature is enabled by this phase.
