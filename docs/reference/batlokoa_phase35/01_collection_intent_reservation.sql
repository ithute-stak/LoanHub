-- FUTURE DESIGN ONLY. NEVER EXECUTE WITHOUT INDEPENDENT APPROVED MIGRATION.
-- Not part of LoanHub's Alembic versions or active payment integrations.
CREATE TABLE IF NOT EXISTS batlokoa_collection_intent_reservations (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES loan_companies(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES client_company_loan(id) ON DELETE RESTRICT,
    borrower_id UUID NOT NULL REFERENCES borrowers(id) ON DELETE RESTRICT,
    idempotency_key VARCHAR(128) NOT NULL,
    request_fingerprint CHAR(64) NOT NULL,
    amount NUMERIC(18,2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'LSL' CHECK (currency = 'LSL'),
    state VARCHAR(24) NOT NULL DEFAULT 'reserved' CHECK (
       state IN ('reserved', 'previewed', 'rejected', 'expired')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_batlokoa_collection_intent_key UNIQUE (company_id, idempotency_key),
    CONSTRAINT ck_batlokoa_collection_intent_fingerprint
        CHECK (request_fingerprint ~ '^[0-9a-f]{64}$')
);
CREATE INDEX IF NOT EXISTS ix_batlokoa_collection_intent_loan
    ON batlokoa_collection_intent_reservations(company_id, loan_id);
-- MUST REVIEW: RLS, role grants, audited events, mandate checks,
-- callback verification, transactional locking and financial reconciliation.
