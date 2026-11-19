# Batlokoa registration — offline completion batch

Branch: `offline/batlokoa-registration-completion-batch-20261119`

This is an **unmerged development branch** based on Phase 91's
`feat/phase91-batlokoa-registration-form-requirements-20261118` branch.
Its purpose is to develop related registration screens and integration
safeguards together, then run comprehensive validation before review.

## Added so far

- `apps/frontend/api/batlokoaRegistration.ts`: typed clients for the
  authenticated read-only registration availability and form requirements
  API. It must never fall back to the legacy `POST /company-clients` route.
- `apps/frontend/app/(dashboard)/company/clients/registration-preview/page.tsx`:
  five-screen navigable registration blueprint, showing planned and deferred
  fields with no client inputs, local PII persistence or submit action.
- Navigation to the preparation screen from company client operations.

## Why client capture is disabled

The existing assisted-client creation endpoint has separate historical
borrower linking behavior. It is not interchangeable with the protected
new-only atomic writer. Creating new accounts against the legacy endpoint
would defeat the protections being built. The protected writer still
requires DBA-reviewed normalized identity indexes, active employee
membership, identity collision screening and an approved release process.

## Remaining batch work before requesting merge

1. Verify Phase 91 metadata and release contract reflect all full-form fields.
2. Implement approved, accessible form UI controls and validation behind a
   separate **non-submitting** integration boundary. No real client details
   should be entered while release approval is pending.
3. Establish and test canonical backend validation contracts, bank encryption
   and current-transaction identity/branch protections for eventual writes.
4. Add complete test coverage for all field mapping, debt and bank rollback,
   idempotency, cross-company access, denied release and legacy history safety.
5. Reconcile any changes to `main`, run frontend typecheck/lint and backend
   isolated PostgreSQL CI tests, and submit one or more reviewable PRs.
6. Independently approve index migration and the deployed release process;
   **do not automatically switch registration on when CI is green**.

The coding maturity goal of 10/10 does not override the independent
production security, DBA, privacy and business approval gates.

## Safety scope

No production deployment, migration, loan calculator, borrower identity
migration, or live Batlokoa new-client registration activation is included.
The new frontend calls GET endpoints only, and captures no customer values.

## Offline iteration 2 — Typed field contract

The authenticated read-only `form-requirements` API now publishes schema
version 2 with descriptive field kinds, required/deferred/sensitive flags,
and the cross-field rule requiring a national ID OR a passport. All keys
are cross-checked against `FullNewOnlyClientCapture`; unexpected schema
drift fails the availability metadata request rather than presenting an
incomplete form.

The frontend preview shows the type and privacy classification of each
field across the five screens. No field values are requested or held in
React state; it still has no form submission code or legacy-registration
fallback.

Automated tests cover type mapping, sensitive fields, mandatory consent
decisions, identity alternatives and rejected metadata drift. This
iteration is committed only to the offline branch; final project CI,
integration tests and merge are deferred pending further development.

## Offline iteration 3 — Strict read-only preview contract gate

The frontend now validates every field and section **before** rendering the
registration preparation screen. An unreviewed schema version, missing field,
reordered section, unsupported field type, demoted sensitive field, changed
required consent, or any enabled new-only write flag causes a fail-closed
error screen. The application deliberately does not send a registration POST
or fall back to the legacy assisted-client creation route.

Automated tests use Node's built-in test runner to execute the **actual
transpiled TypeScript guard**; they cover valid metadata plus altered field
inventory, identity alternatives, privacy labels, deferred fields and
forged enabling status.

To run this focused test locally, from `apps/frontend` after dependencies
are installed:

```bash
pnpm test:batlokoa-registration-preview
```

These branch changes have not been run through the full frontend typecheck,
backend tests or GitHub CI. The batch is intentionally not merged or
deployed yet.

## Offline iteration 4 — Realistic, disabled screen controls

All five planned registration screens now show actual accessible UI elements
for reviewed field kinds. Text, dates and numeric placeholders use disabled
inputs; consent uses disabled unchecked checkboxes; banking, debts and
employer-group fields show explanatory read-only panels.

The user cannot type a real name, national ID, passport, salary, bank
account or consent into this preview. There is no draft persistence, POST
request, login credential capture or legacy assisted-registration fallback.

`apps/frontend/tests/batlokoa-registration-readonly-components.test.mjs`
parses the actual TSX components and asserts every input/checkbox is
disabled and has no change handler or implicit captured value. It also
checks the preview page and typed API client have no mutation calls.
These checks run together with the schema-drift tests:

```bash
cd apps/frontend
pnpm test:batlokoa-registration-preview
```

Full CI and deployed-browser testing remain pending; the branch is not
merged or deployed.

## Offline iteration 5 — Tenant and branch authorization hardening

The authenticated Batlokoa **informational** registration endpoints now
require a complete active, approved company context, authoritative UUID
company and employee identities, matching staff/company/user links, active
lending staff and a matching assigned branch for non-management roles.
Management roles may inspect the static form metadata without an assigned
branch; neither role can submit a new-only registration.

Regression tests reject revoked/inactive staff, inactive or pending
companies, cross-company mismatches, wrong branches and malformed
authoritative identifiers, and ensure neither preview API accepts a body.

The checks complement (and do NOT replace) the database-locked staff,
branch, index, global identity and idempotency checks that must be
performed inside any eventual new-only write transaction. These metadata
endpoints still return a constant disabled registration state.

The offline branch is still unmerged; isolated full backend and frontend
CI certification is pending.

## Offline iteration 6 — New-client to loan-application handoff

A standalone internal, read-only verifier now checks that a prospective
loan handoff references a **completed** new-only registration from the
same company, assigned branch and originating employee. Both the company
account and final registration attempt must match. Legacy assisted
registrations, absent or incomplete idempotency records, old/historical
borrower accounts, wrong branch or employee IDs, unapproved tenants and
non-PostgreSQL database connections are denied.

The service returns a fixed assessment with
`can_create_loan_application=False` and `can_disburse_loan=False`;
it does not invoke LoanHub origination, payments, loan calculator,
credit decisioning or client mutation. It has **no public router** and
is not a substitute for future read-time DB role locks or underwriting.

The last registration preview screen now shows a disabled loan handoff
button and a checklist for KYC, affordability and credit approval.
The focused frontend tests verify no loan origination or calculator
call is wired to the preview.

Backend unit tests cover completed registration provenance, replay
mismatches, stale status, historic source, cross-company, cross-branch,
revoked/invalid staff and no write calls. These new tests are committed
but NOT certified by CI. Future end-to-end work must check real
PostgreSQL transaction behavior and loan product, policy and application
idempotency before any live handoff.

## Offline iteration 7 — Loan product and duplicate application preflight

The internal loan-handoff path now has a separate, **read-only** origination
preflight that first requires protected new-only registration provenance.

It enforces active tenant-owned loan product identity, finite two-decimal
positive principal, the loan product's minimum/maximum amount and term, and
a conservative search for **any existing direct origination application**
for this borrower across all companies/statuses. A previous application
blocks new-only progression even if rejected or completed, pending a
separately reviewed repeat-lending policy.

This preflight is not the LoanHub calculator, is not a credit decision, and
does not issue a loan, create a draft, reserve an idempotency key, or
disburse funds. Successful checks still return
`can_create_loan_application=False` and `can_disburse_loan=False`.
KYC, affordability, human underwriting and independent release
authorization remain separate prerequisites.

Added targeted mocked-DB unit tests cover good provenance with disabled
write outcome, mismatched product/company/borrower/branch, invalid values,
amount/term boundaries, pre-existing application and missing records,
including explicit assertions that no database mutation methods are called.

These tests are not yet CI-certified, and this is NOT a concurrency-safe
unique application reservation. Eventual writes require fresh database
locking and real PostgreSQL repeat/parallel request tests. The offline
branch has not been merged or deployed.
