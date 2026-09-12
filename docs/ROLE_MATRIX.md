# Role Matrix

| Role | Scope | Main capabilities |
|---|---|---|
| `superadmin` | Entire platform | Approve/suspend tenants, manage plans, inspect companies, branches, requests, loans and payments |
| `company_owner` | Entire selected company | Full tenant configuration, branches, staff, products, billing, marketplace, loans and finance actions |
| `company_admin` | Entire selected company | Same operational tenant controls as owner, except protected owner-account operations |
| `branch_manager` | Assigned branch | Branch staff visibility, marketplace/offers, branch loans and collections visibility |
| `loan_officer` | Assigned branch when configured | Redacted marketplace, paid unlocks, offers and loan visibility |
| `finance_officer` | Assigned branch when configured | Loan visibility, disbursement and company/branch payment operations |
| `collections_officer` | Assigned branch when configured | Loan, repayment and overdue-account visibility |
| `compliance_officer` | Company or assigned branch | Read-only operational review and compliance visibility |
| `auditor` | Company or assigned branch | Read-only records and payment/loan review |
| `customer_support` | Company or assigned branch | Read-only customer and case-support visibility |
| `borrower` | Own account only | Profile, requests, offers, accepted loans and repayments |

## Important behavior

- Company owners and administrators are company-wide even when a branch ID is accidentally present on their membership.
- Other company roles become branch-scoped when assigned to a branch.
- The global `users.role` identifies the account family, while the authoritative role for a selected tenant is the `company_staff.role` membership.
- Frontend navigation improves usability, but backend permission checks are the security boundary.
