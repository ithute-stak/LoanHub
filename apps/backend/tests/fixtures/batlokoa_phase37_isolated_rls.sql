-- PHASE 37 TEST FIXTURE ONLY. NOT AN ALEMBIC/PRODUCTION MIGRATION.
-- Execute ONLY in an isolated schema with disposable fake company/loan/borrower IDs.
-- Runtime actor must be a restricted non-owner role without BYPASSRLS.
-- Transaction GUCs are trusted only when installed by authenticated application
-- code, not by untrusted SQL users. No real payment or customer tables are used.
CREATE TABLE phase37_company (
    company_id uuid PRIMARY KEY
);
CREATE TABLE phase37_loan (
    company_id uuid NOT NULL REFERENCES phase37_company(company_id),
    loan_id uuid NOT NULL,
    PRIMARY KEY(company_id, loan_id)
);
CREATE TABLE phase37_borrower (
    company_id uuid NOT NULL REFERENCES phase37_company(company_id),
    borrower_id uuid NOT NULL,
    PRIMARY KEY(company_id, borrower_id)
);
CREATE TABLE phase37_reservation (
    reservation_id uuid PRIMARY KEY,
    company_id uuid NOT NULL,
    loan_id uuid NOT NULL,
    borrower_id uuid NOT NULL,
    amount numeric(18,2) NOT NULL CHECK(amount > 0),
    request_fingerprint char(64) NOT NULL,
    idempotency_key varchar(128) NOT NULL,
    UNIQUE(company_id, idempotency_key),
    FOREIGN KEY(company_id,loan_id) REFERENCES phase37_loan(company_id,loan_id),
    FOREIGN KEY(company_id,borrower_id) REFERENCES phase37_borrower(company_id,borrower_id)
);
ALTER TABLE phase37_reservation ENABLE ROW LEVEL SECURITY;
ALTER TABLE phase37_reservation FORCE ROW LEVEL SECURITY;
CREATE POLICY phase37_tenant_select ON phase37_reservation
    FOR SELECT USING (
        current_setting('loanhub.actor_scope', true) = 'tenant'
        AND company_id::text = current_setting('loanhub.company_id', true)
    );
CREATE POLICY phase37_tenant_insert ON phase37_reservation
    FOR INSERT WITH CHECK (
        current_setting('loanhub.actor_scope', true) = 'tenant'
        AND company_id::text = current_setting('loanhub.company_id', true)
    );
-- No UPDATE, DELETE or TRUNCATE grant/policies: fail closed for application role.
