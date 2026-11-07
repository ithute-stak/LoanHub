# Batlokoa collection-preview authorization boundary

This phase adds a **read-only authorization service**, not a public API route
or payment initiation workflow. It must be invoked only after LoanHub has
authenticated the request and resolved the trusted `TenantContext`.

The service queries the existing `ClientCompanyLoan` and `Borrower`
records. It fails closed unless:

- Active, non-platform company staff has a permitted finance or collections role.
- The active membership and tenant context belong to the exact registered
  Batlokoa company.
- The requested loan is associated with that company.
- Non-management staff are scoped to the loan's assigned branch.
- The borrower row matches the loan's borrower FK and the verified borrower
  user UUID supplied by the trusted calling domain layer.
- The loan was disbursed and remains active/defaulted, with positive balance.
- The requested preview amount is positive, valid LSL cents and not greater
  than the currently recorded balance.

The service returns only a verified company/loan/borrower scope, a normalized
amount and a deterministic opaque loan reference. It does not access the
IthutePay API, reserve an idempotency key, grant a payment mandate,
post to an account, or move funds. Approval of a collection **preview**
must never be reused as authorization to debit a borrower.

No route exposes this service yet. Future routes must also verify a user's
authenticated session and source of borrower identity, and must recheck the
loan/balance before actual posting. Provider contractual and regulatory
authorization, transactional idempotency, mandate controls, balance locking,
settlement and reconciliation remain separate requirements.

No environment changes or production deployment are part of this phase.
