# LoanHub v1.1 Professional Lending Expansion

Adds direct/walk-in loan applications, shared credit checks with consent, automatic 365-day blacklist records, company suggestions, public offer-wall posts, payment receipt data structures, revocable local print agents/jobs, and an in-system guidance assistant.

## Important boundaries
- M-Pesa, EcoCash and EFT live settlement still require official provider/bank credentials, callback verification, reconciliation and certification. This release provides the internal domain foundation, not a false live integration.
- Cross-lender credit disclosure must be governed by borrower consent, applicable Lesotho law, contracts and platform privacy policy.
- The assistant is a deterministic product guide. Connecting a general-purpose AI model requires a separately secured provider integration and data-governance review.
- The print bridge is source code for a local service. Production distribution should use code signing, OS keyring storage, automatic updates and a revocable agent secret.

## Migration
`a7c91d2e4f10` follows `f1a9c4e7b620`. Back up first, stop API/workers, then run `alembic upgrade head`.
