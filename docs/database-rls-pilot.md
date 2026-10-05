# PostgreSQL RLS Pilot

LoanHub's first database-level tenant-isolation pilot covers only internal,
company-owned operational tables:

- `crm_relationship_cases`
- `collateral_assets`
- `legal_recovery_matters`

The pilot deliberately excludes borrower-facing, public, shared-identity and
provider-wide tables.

## Context source

Policies consume transaction-local settings created from LoanHub's verified
authorization context:

- `loanhub.user_id`
- `loanhub.company_id`
- `loanhub.branch_id`
- `loanhub.role`
- `loanhub.actor_scope`

Raw request headers are not written directly into PostgreSQL tenant context.

## Policy behaviour

Tenant actors can only see or mutate rows where `company_id` equals the
verified active company.

Platform roles have explicit policy-level access rather than a generic bypass.
All recognised platform roles may read the three pilot tables, while only
`superadmin`, `platform_admin`, and `platform_operations` may mutate them.
Borrower scope has no policy path to these internal tables.

Application authorization remains mandatory. RLS is a second defensive layer,
not a replacement for route-level role, branch, or ownership checks.

## Operational dependency

The runtime application role must not own these tables. PostgreSQL table owners
normally bypass RLS unless `FORCE ROW LEVEL SECURITY` is enabled. LoanHub
intentionally does not use FORCE in this pilot because schema owners and
migration sessions must retain administrative access. Production enforcement
therefore depends on the restricted non-owner runtime role from the DBMS
least-privilege phase.

## Expansion gate

Do not expand RLS to additional tables until all of the following are proven:

1. restricted runtime-role deployment is active;
2. tenant context is present after normal request commits;
3. cross-company SELECT, INSERT, UPDATE and DELETE attempts are denied;
4. platform read/write role distinctions behave as intended;
5. backup/restore and migrations remain operational;
6. no borrower/public flow depends on one of the protected tables.
