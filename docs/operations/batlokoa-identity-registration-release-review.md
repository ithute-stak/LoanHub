# Batlokoa new-only registration: identity reconciliation and release review

**Classification:** operational change-control runbook. **State:** not approved.  
**Scope:** LoanHub shared global identities and historical loan capture linkage.  
**This document authorizes no database change, borrower relink, account merge, or registration activation.**

## Verified operator snapshot — 2026-11-24

Preliminary aggregate read-only SQL inspection (not a formally credentialed independent audit) indicated:

| Check | Groups / rows |
| --- | ---: |
| Normalized National ID / passport / user phone / user email duplicate groups | 0 / 0 / 0 / 0 |
| Blank identity-field rows (four fields) | 0 |
| Legacy National ID groups intersecting existing people | 113 |
| Linked-only groups | 96 |
| Mixed linked and unlinked groups | 15 |
| Unlinked-only groups | 2 |
| Legacy rows with no borrower link | 17 |
| Unlinked rows with a single borrower and a same-company account as **candidate evidence** | 17 |
| Historical passport overlap groups | 6 |
| Repeated historical passport groups | 0 |
| Normalized unique indexes present | 0 of 4 |

**Do not treat the 113 overlaps as 113 duplicate borrowers.** Existing linked captures may be valid historical loans. The **17 unresolved identity groups** and **6 passport overlap groups** need authorized human review; some passport cases may overlap the National ID cases.

## Controlled review sequence

1. **Identity and record owner:** Authorized lending-domain reviewer creates an access-controlled case for each unresolved identity group, without publishing names, National IDs, passport numbers, phone numbers, or borrower IDs to CI artifacts, PR comments or external tickets.
2. **Source-of-truth check:** In the protected operator environment, compare verified identity documents, historical capture evidence, the global person/user identity, existing borrower, company-scoped borrower account, and loan ownership. Record whether linkage is already correct, a missing link is confirmed, a conflicting person exists, or the evidence is inconclusive.
3. **Tenant separation:** Confirm company ID and branch provenance independently. Never infer permission to link or merge from a matching National ID or the existence of one same-company account alone.
4. **Second reviewer:** Lending-domain owner and privacy/security reviewer independently approve or reject each proposed remediation. Maintain immutable evidence and actor/timestamp records in the authorized system.
5. **Remediation:** Apply any separately approved correction only through a reviewed idempotent migration/administrative command with per-case verification and a rollback plan. No automated reconciliation is included in this change.
6. **Re-audit:** Run the dedicated read-only aggregate audit again and record results using the approved read-only database role. Keep registration disabled if any unresolved or contradictory evidence remains.

### Case decision record (stored only in authorized case management)

- Case reference: opaque, non-PII review ID
- Category: mixed linkage / unlinked-only / passport overlap / other
- Tenant ownership and identity evidence: protected attachment references, **never copied into GitHub**
- Decision: verified legitimate linkage / approved correction / no action / unresolved
- Two independent reviewer identities and timestamps
- Authorized change reference and rollback reference, if a correction was approved
- Post-change independent verification: pass / fail / pending

## Four normalized uniqueness indexes

The proposed index definitions are maintained as **review-only** constants in `apps/backend/services/identity_index_readiness.py`:

- `uq_people_national_id_normalized`
- `uq_people_passport_normalized`
- `uq_users_phone_normalized`
- `uq_users_email_normalized`

An authorized DBA must review the exact expressions, partial predicates, collation, invalid leftovers, concurrent-build locking/long transaction risks, backup and rollback strategy, and the collision audit immediately before any production DDL. Index build must be performed under a separate approved change request; never run it from CI or this document. The writer's exact index preflight must pass after creation.

## Release decision checklist

- [ ] All historical case reviews are documented and signed off; unresolved cases are dispositioned by authorized reviewers
- [ ] Dedicated read-only audit credentials verified; fresh aggregate report preserved in approved secure audit storage
- [ ] Four normalized indexes independently DBA-reviewed, installed, structurally verified and monitored
- [ ] All other historical identity writers assessed for uniqueness and race conditions
- [ ] Lending-domain owner approval recorded
- [ ] Privacy/security approval recorded
- [ ] DBA approval recorded
- [ ] Production change-control approval recorded
- [ ] Draft LoanHub registration route reviewed and explicitly released with authenticated tenant/branch/actor context
- [ ] Batlokoa gateway and UI explicitly released; CSRF, idempotency and full sensitive payload tested
- [ ] Isolated full HTTP-to-PostgreSQL readback and duplicate/retry tests pass
- [ ] Authenticated production pilot with documented consent and rollback succeeds

**Fail-closed rule:** All boxes must be independently evidenced before live Save Client can be enabled. A green CI run, zero duplicate counts, or a successful Docker image build is never an authorization by itself.

Related work: LoanHub PR #876 (read-only historical review), draft PR #840 (disabled writer), Batlokoa PRs #88–#90 (staged gateway and review UI).
