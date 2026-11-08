-- OFFLINE REFERENCE DESIGN ONLY. NOT A MIGRATION. DO NOT RUN ON PRODUCTION.
-- All these names are illustrative, not guaranteed to match LoanHub schema.
-- Real deployment needs reviewed FK constraints, RLS, restricted runtime roles,
-- a transactional migration, tested rollback, backups and approved mandates.
-- The following illustrates the intended durable uniqueness boundaries.

CREATE TABLE IF NOT EXISTS proposed_collection_operations (
  operation_id uuid PRIMARY KEY,
  company_id uuid NOT NULL,
  loan_id uuid NOT NULL,
  borrower_id uuid NOT NULL,
  idempotency_key varchar(128) NOT NULL,
  request_fingerprint char(64) NOT NULL,
  amount numeric(18,2) NOT NULL CHECK (amount > 0),
  currency varchar(3) NOT NULL CHECK (currency='LSL'),
  status varchar(32) NOT NULL DEFAULT 'reserved',
  version bigint NOT NULL DEFAULT 0 CHECK(version >= 0),
  provider_reference varchar(128),
  UNIQUE (company_id,idempotency_key),
  UNIQUE (company_id,operation_id),
  CHECK(status IN ('reserved','mandate_verified','submitted','unknown',
       'failed','settled','reversal_requested','reversed'))
);

CREATE TABLE IF NOT EXISTS proposed_collection_events (
  event_id uuid PRIMARY KEY,
  company_id uuid NOT NULL,
  operation_id uuid NOT NULL,
  version bigint NOT NULL CHECK(version > 0),
  kind varchar(32) NOT NULL,
  payload_digest char(64) NOT NULL,
  prior_digest char(64),
  event_digest char(64) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(company_id,operation_id,version),
  FOREIGN KEY(company_id,operation_id)
    REFERENCES proposed_collection_operations(company_id,operation_id)
);

CREATE TABLE IF NOT EXISTS proposed_collection_outbox (
  message_id uuid PRIMARY KEY,
  company_id uuid NOT NULL,
  event_id uuid NOT NULL REFERENCES proposed_collection_events(event_id),
  topic varchar(128) NOT NULL,
  delivered_at timestamptz,
  attempts integer NOT NULL DEFAULT 0 CHECK(attempts >= 0),
  UNIQUE(company_id,event_id,topic)
);

CREATE TABLE IF NOT EXISTS proposed_provider_events (
  event_id uuid PRIMARY KEY,
  company_id uuid NOT NULL,
  operation_id uuid NOT NULL,
  provider varchar(40) NOT NULL,
  provider_event_reference varchar(128) NOT NULL,
  provider_transaction_reference varchar(128) NOT NULL,
  verification_version varchar(40) NOT NULL,
  payload_sha256 char(64) NOT NULL,
  outcome varchar(32) NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(provider,provider_event_reference),
  FOREIGN KEY(company_id,operation_id)
    REFERENCES proposed_collection_operations(company_id,operation_id)
);

CREATE TABLE IF NOT EXISTS proposed_financial_journals (
  journal_id uuid PRIMARY KEY,
  company_id uuid NOT NULL,
  operation_id uuid NOT NULL,
  posting_key varchar(128) NOT NULL,
  policy_version varchar(128) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(company_id,posting_key),
  UNIQUE(company_id,operation_id,posting_key),
  FOREIGN KEY(company_id,operation_id)
    REFERENCES proposed_collection_operations(company_id,operation_id)
);

CREATE TABLE IF NOT EXISTS proposed_financial_lines (
  line_id uuid PRIMARY KEY,
  journal_id uuid NOT NULL REFERENCES proposed_financial_journals(journal_id),
  account_ref varchar(128) NOT NULL,
  debit numeric(18,2) NOT NULL DEFAULT 0 CHECK(debit >= 0),
  credit numeric(18,2) NOT NULL DEFAULT 0 CHECK(credit >= 0),
  CHECK ((debit>0 AND credit=0) OR (credit>0 AND debit=0))
);
-- NOTE: balance across journal lines requires a posting service in a locked
-- transaction, or deferred constraint trigger; per-line checks are insufficient.
-- NOTE: provider_event uniqueness must be researched per provider event model.
-- NOTE: references must use actual LoanHub composite tenant FKs before approval.
-- NOTE: append-only is NOT achieved by CREATE TABLE; use restricted grants,
-- write-once service layer, audit chain anchoring and verified ops controls.
-- NOTE: do not automatically retry UNKNOWN provider responses.
