# Release / test matrix (not a claim of production certification)

| Concern | Offline code/tests | Still needed for production |
|---|---|---|
| Valid mandate | `completion_engine/mandates.py` | Identity + consent-verifier connection, revocation registry, legal audit |
| Provider callbacks | `callback_intake.py`, `provider_event_store.py` | Actual documented Vodacom/Econet/Golink adapter, TLS, secrets, sandbox certification |
| Multi-merchant | `provider_registry.py` | Production merchant ownership and permitted master-merchant custody contracts |
| Transaction durability | `atomic_repository.py`, optional PG tests | Approved LoanHub/Alembic schema, real ledger locking, RLS, transaction-bound ORM adapter |
| Journal accounting | Existing `remaining_engine/ledger_posting.py` | Actual chart of accounts, independent policy approval, postings and refunds |
| Pricing | `fee_policy.py` | Approved agreements and independently verified provider fees |
| Outbox | `outbox_worker.py` | Reliable leasing, workers, delivery ACKs, dead-letter operations/monitoring |
| Recovery | `recovery.py` | Verified provider status API, manual unknown-state resolution |
| Reconciliation | Existing `remaining_engine/reconciliation.py` | Authenticated statements, bank settlement, exception operations |
| Audit | Existing `remaining_engine/audit_outbox.py` | Immutable protected DB roles, anchored digests, audit export |
| Tenant security | Existing Phase 37 tests | Real relation foreign keys, PostgreSQL RLS and runtime user policies |
| Load/failure | Unit tests, optional synthetic DB tests | Chaos load, rate limiting, restore tests, HA/DR evidence |

**Scope:** The package aims to cover implementation-ready offline contracts and integration scaffolding. It cannot constitute the complete live financial application by itself.
