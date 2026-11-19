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
