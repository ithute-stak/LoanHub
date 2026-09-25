# CDAS reintegration branch

This branch rebuilds LoanHub's CDAS integration from the official third-party API contract, while deliberately excluding the failed autonomous/background integration model.

## Implemented manual CDAS capabilities

- encrypted company-scoped CDAS credentials
- TEST/LIVE endpoint validation
- authentication via `POST /api/security/login`
- manual employee verification via `/api/employee/getDetails`
- manual affordability checks via `/api/employee/check-affordability`
- manual all-third-party deduction lookup via `/api/policy/view-all-deduction`
- manual own-deduction lookup via `/api/policy/view-deduction`
- manual active/approved deduction lookup via `/api/policy/get-active-and-approved-deduction`
- management-only deduction lifecycle requests via `/api/policy/add-update-deduction`
- management-only active-deduction modification via `/api/policy/modify-active-deduction`
- management-only settlement via `/api/policy/settled-deduction`
- management-only output-file/statement retrieval via `/api/policy/get_document`
- explicit confirmation before every state-changing provider operation
- best-effort LoanHub audit logging around provider mutations
- local 400-requests-per-day protection keyed by hashed CDAS username and environment
- local request-budget status display that does not contact CDAS
- safe session reauthentication for read-only calls
- no automatic replay of state-changing requests after token/session failure
- clean `/company/cdas` workspace with old CDAS booking URLs reduced to compatibility redirects

## Intentionally excluded

The following old runtime behaviour remains disabled and must not be restored casually:

- background CDAS crawling
- roster discovery or employee sync workers
- scheduled CDAS polling, including the former 03:45 workflow
- automatic affordability or deduction refresh
- automatic booking or deduction lifecycle progression
- portfolio intelligence crawling
- automatic CDAS KPI harvesting
- growth/decay forecasting based on autonomous provider reads
- opportunity generation
- any uncontrolled bulk CDAS operation

Historical database models and Alembic migrations are retained where required for migration safety. Their presence does not mean the old runtime behaviour is active.

## Safety rules

1. CDAS provider calls are user-initiated unless a future change is separately designed, reviewed and approved.
2. Read-only calls may obtain a fresh session and retry once when the provider reports an inactive/expired session.
3. State-changing calls are never automatically replayed. A retry must be a new explicit user action.
4. LoanHub must stop locally when the configured CDAS API account reaches the documented daily request allowance.
5. Production credentials must never be committed to the repository.
6. Real deduction registration, modification or settlement must not be used merely as a smoke test.
7. This branch must not be merged or deployed to production until controlled TEST-environment UAT is complete and production approval is explicit.

## Acceptance sequence

Provider acceptance should proceed in this order:

1. TEST authentication
2. employee verification
3. affordability
4. all-third-party deductions
5. own deductions by status
6. active/approved deduction lookup
7. output-file/statement retrieval
8. controlled TEST deduction registration
9. review/approval/update flow
10. active-deduction modification
11. settlement

The read-only sequence should be completed before any TEST deduction mutation is attempted.
