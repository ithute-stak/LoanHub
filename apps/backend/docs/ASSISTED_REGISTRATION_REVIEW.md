# Assisted registration review — LoanHub Phase 62

This change adds a read-only endpoint:
`POST /api/v1/company-clients/registration-review`, body
`{"national_id":"...", "branch_id":"<authorized branch UUID>"}`.

It requires an authenticated **lending staff** LoanHub session, active
tenant membership, and native `assert_branch_scope` authorization.
The national ID is sent in the HTTPS request body, not query parameters.

The server checks for a matching existing person, company-scoped
borrower loan exposure, and company-scoped legacy capture records. Only a
coarse decision is returned, no raw identity or financial details.

**Critical:** `can_commit` is always `false`. Even a clean lookup
only reports `new_identity_candidate`, not permission to submit.
The existing `POST /company-clients` behavior is unchanged: it may
reuse national-ID matched borrowers and modify their shared profiles.
Do not connect Batlokoa's registration-submit button to that existing
write endpoint without a separate transactional safe-create workflow,
identity evidence checks, idempotency, and legacy data remediation.

This is preparatory infrastructure only. No migrations, customer data
writes, deployments or payments are included. Review endpoint must be
staging-tested before use with real data.
