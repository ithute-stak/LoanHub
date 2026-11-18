# Phase 76 — Active staff and branch authorization for new-only registration

The Phase 75 disposable PostgreSQL registration tests passed. Before any
API exposure, Phase 76 strengthens the internal authorization boundary:

- Only a verified active `CompanyStaff` membership, bound to the same LoanHub
  user and company, may prepare the registration intent.
- The LoanHub user must be active and the selected staff role must be an
  approved lending role. The generic platform-admin role bypass is deliberately
  rejected for client registration.
- Loan officers and other non-company-management staff must have a concrete
  assigned branch; the selected branch must match that assignment.
- Company owners/admins may select any branch *only if* it exists and is
  active in their own company. This is confirmed with a PostgreSQL row
  query inside the registration transaction.
- The internal write service rejects missing, inactive or cross-company
  branches before identity reservation or new-client staging.
- Regression tests cover platform administrators, suspended staff, inactive
  users, incorrect membership company/user, branchless staff and missing
  company-owned branches.
- The isolated end-to-end PostgreSQL fixture uses active synthetic branch
  rows to exercise the same real SQLAlchemy branch query.

This is still an internal service with no API route. The production
normalized unique identity index migration remains blocked on real-world
collision audits and all writer compatibility; the Batlokoa client
registration feature remains off.

No production borrower, historical loan, repayment or settlement records
are modified in this phase.
