-- CI/DEVELOPMENT SCHEMA ONLY. DO NOT APPLY TO ANY PRODUCTION DATABASE.
-- Synthetic tables; full LoanHub tenant/FK/RLS/migration review is pending.
CREATE TABLE phase42_operations (
 company_id UUID NOT NULL, operation_id VARCHAR(128) NOT NULL,
 version INTEGER NOT NULL CHECK(version>=0),
 status VARCHAR(32) NOT NULL CHECK(status IN ('reserved','mandate_verified','submitted','unknown','failed','settled','reversal_requested','reversed')),
 amount NUMERIC(18,2) NOT NULL CHECK(amount>0), PRIMARY KEY(company_id,operation_id)
);
CREATE TABLE phase42_journals (
 company_id UUID NOT NULL,operation_id VARCHAR(128) NOT NULL,
 posting_key VARCHAR(128) NOT NULL,policy_id VARCHAR(128) NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY(company_id,posting_key),
 FOREIGN KEY(company_id,operation_id) REFERENCES phase42_operations(company_id,operation_id)
);
CREATE TABLE phase42_journal_lines (
 company_id UUID NOT NULL,posting_key VARCHAR(128) NOT NULL,
 line_no INTEGER NOT NULL CHECK(line_no>0),account VARCHAR(128) NOT NULL,
 side VARCHAR(8) NOT NULL CHECK(side IN ('debit','credit')),
 amount NUMERIC(18,2) NOT NULL CHECK(amount>0),
 PRIMARY KEY(company_id,posting_key,line_no),
 FOREIGN KEY(company_id,posting_key) REFERENCES phase42_journals(company_id,posting_key)
);
CREATE TABLE phase42_posting_events (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 company_id UUID NOT NULL,operation_id VARCHAR(128) NOT NULL,
 posting_key VARCHAR(128) NOT NULL,kind VARCHAR(64) NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(company_id,posting_key,kind),
 FOREIGN KEY(company_id,posting_key) REFERENCES phase42_journals(company_id,posting_key)
);
CREATE TABLE phase42_outbox (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 company_id UUID NOT NULL,operation_id VARCHAR(128) NOT NULL,
 posting_key VARCHAR(128) NOT NULL,topic VARCHAR(128) NOT NULL,
 delivered_at TIMESTAMPTZ NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(company_id,posting_key,topic),
 FOREIGN KEY(company_id,posting_key) REFERENCES phase42_journals(company_id,posting_key)
);
CREATE TABLE phase42_provider_events (
 company_id UUID NOT NULL,provider VARCHAR(80) NOT NULL,
 event_id VARCHAR(128) NOT NULL,operation_id VARCHAR(128) NOT NULL,
 provider_tx_id VARCHAR(128) NOT NULL,raw_digest CHAR(64) NOT NULL,
 outcome VARCHAR(16) NOT NULL CHECK(outcome IN ('settled','failed','reversed')),
 amount NUMERIC(18,2) NOT NULL CHECK(amount>0),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY(company_id,provider,event_id),
 FOREIGN KEY(company_id,operation_id) REFERENCES phase42_operations(company_id,operation_id)
);
-- Production: real FK mapping, tenant RLS, DB access roles and immutable
-- evidence/ledger posting authorization are mandatory. No grant here.
