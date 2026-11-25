# Branch cash controls — historical session reconciliation gate

**Status:** operational review procedure only. This document does not authorise writes, backfills, session closure, policy changes, or feature activation.

## Purpose

Cash controls must not be activated solely because accounting journals and Treasury projections agree. A historical session can still be open, lack its Finance Desk-to-Treasury opening link, or have no independently verified physical cash count.

## Known exception requiring evidence

- Business date: **2026-10-21**
- Recorded opening: **M10.00**
- Posted accounting cash movement: **+M2,320.00**
- Treasury cash movement: **+M2,320.00**
- Computed position: **M2,330.00**
- Historical cash session: **open**
- Finance Desk opening-session Treasury link: **missing**

These figures are historical observations, not a current database attestation. Re-run the approved read-only audit before making decisions. **M2,330.00 is not a verified physical count.**

## Investigation and evidence

1. Identify the exact tenant, branch, session ID and business date under an authorised company-scoped read-only role. Do not include borrower personal data in audit exports.
2. Run `python -m scripts.audit_branch_cash_readiness --company-id <UUID> --from-date <earliest-session-date> --to-date <today>` with `LOANHUB_CASH_AUDIT_DATABASE_URL` set to an authorised *read-only* database connection. Do not assume a narrow date range can certify readiness.
3. Preserve the output and audit time, database environment identifier, application revision, query/report version and investigating officer.
4. Obtain contemporaneous till count, signed cashbook or reconciliation sheets, handover reports, recorded opening source, receipt and disbursement vouchers, and supervisor verification where they exist. If evidence is missing, record that fact rather than inventing a count.
5. Review the accounting journal and Treasury cash movements transaction by transaction. Identify any timing differences, duplicates, voids, posting-status differences or unlinked opening rows; reconcile by source ID/reference without altering journals.
6. Confirm whether the session really remained operationally open or whether a recorded but unsynchronised closure exists. Do not equate an expected close with an actual verified cash count.

## Authorisation and resolution

- An independent reviewer records findings, outstanding discrepancies, evidence references, and a proposed resolution.
- A company-authorised approver reviews the recommendation. The creator and approver should be different people.
- Any historical correction or closure requires a separately designed and tested, tenant/branch-restricted, idempotent, audit-logged workflow. The workflow must preserve original entries and record actor, reason, references, timestamps and before/after state.
- Do **not** directly `UPDATE` financial tables, insert a balancing journal, invent physical cash, or silently replace historical opening amounts.
- If sufficient evidence for a historical counted close is unavailable, keep the exception unresolved and block activation for the affected company.

## Release gate checklist

- [ ] Fresh full CI and disposable PostgreSQL integration checks pass on the exact intended PR head
- [ ] Tenant/branch isolation and simultaneous loan payout/expense/closing tests are certified against actual service paths
- [ ] Entire company cash-session history is included in the audit; no truncated or excluded sessions
- [ ] Historical session exceptions are resolved with documented approvals or remain explicit blockers
- [ ] The audit is rerun after each approved remediation with a stable consistent read-only snapshot
- [ ] An independent owner/security/finance release approval is recorded
- [ ] A separately reviewed activation command/workflow, rollback strategy and post-activation monitoring plan are in place

**Fail closed:** a clean read-only report is necessary, not sufficient, for activation. Do not change `enforce_branch_cash_controls_enabled` through routine company settings or deploy a bypass.
