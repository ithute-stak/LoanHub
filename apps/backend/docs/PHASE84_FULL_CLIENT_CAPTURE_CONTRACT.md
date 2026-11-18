# Phase 84 — Complete registration capture contract (not a write API)

The existing client creation service only persists a minimal subset and
deliberately refuses the remainder. It must not be made available to Batlokoa
employees under a full-form screen without a safe storage path.

This phase adds `FullNewOnlyClientCapture`, a **strict, non-persistent**
schema derived from the existing assisted LoanHub client form. It preserves
all currently supported registration fields, including employer, salary,
address, banking input, and declared external debts. Unknown keys are
rejected rather than silently ignored.

Its explicit conversion to `AssistedCompanyClientCreate` is lossless for
validated fields; the Phase 83 minimal atomic writer remains unchanged and
still rejects extra financial fields.

The new contract additionally requires a selected branch, an identity
document, a past birth date, and consistent declaration of external debt.
These checks are not credit or KYC approval. Existing external loans are
only user declarations and must not be inserted or treated as settled
LoanHub obligations.

Before live staff registration, implement **transactional storage** for
the full form, including encrypted bank details, separate external debt
rows, employer group authorization, appropriate consent and field
access policies, and all foreign keys. Test rollback of the entire
multi-table operation, and retain the legacy collision rules, idempotency,
normalized uniqueness constraints and current employee database checks.

No public API, production migration, feature flag, client creation, loan
repayment or loan calculator changes are introduced here.
