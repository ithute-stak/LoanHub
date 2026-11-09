-- BFS folio correction: S/E covers days 27-31 and 1-14.
-- Run in a controlled maintenance window AFTER a tested database backup.
-- This script changes existing folio identifiers, including identifiers referenced
-- in generated contracts/receipts. Obtain accounting/legal approval and preserve
-- the audit mapping for historical document lookups before applying.
-- Idempotent: already-correct S/E loans are never renumbered.
BEGIN;
SET LOCAL lock_timeout = '15s';
SET LOCAL statement_timeout = '5min';
LOCK TABLE client_company_loan IN SHARE ROW EXCLUSIVE MODE;

CREATE TABLE IF NOT EXISTS bfs_folio_group_correction_audit (
    loan_id uuid PRIMARY KEY,
    company_id uuid NOT NULL,
    old_folio_number varchar(40) NOT NULL,
    new_folio_number varchar(40) NOT NULL,
    old_group_code varchar(8) NOT NULL,
    new_group_code varchar(8) NOT NULL DEFAULT 'S/E',
    old_sequence integer NOT NULL,
    new_sequence integer NOT NULL,
    contractual_pay_day integer NOT NULL,
    corrected_at timestamptz NOT NULL DEFAULT now()
);

CREATE TEMP TABLE bfs_se_folio_changes ON COMMIT DROP AS
WITH eligible AS (
    SELECT l.id, l.company_id, l.created_at,
           l.folio_number AS old_folio_number,
           l.folio_group_code AS old_group_code,
           l.folio_sequence AS old_sequence,
           COALESCE(
             NULLIF(l.preferred_payment_day, 0),
             EXTRACT(DAY FROM l.first_payment_due)::integer,
             CASE WHEN (l.calculation_breakdown #>> '{schedule_rows,0,due_date}')
                           ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
               THEN EXTRACT(DAY FROM (l.calculation_breakdown #>> '{schedule_rows,0,due_date}')::date)::integer
             END,
             CASE WHEN (l.calculation_breakdown #>> '{due_dates,0}')
                           ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
               THEN EXTRACT(DAY FROM (l.calculation_breakdown #>> '{due_dates,0}')::date)::integer
             END
           ) AS pay_day
    FROM client_company_loan l
    WHERE l.folio_company_code = 'BFS'
      AND l.folio_group_code <> 'S/E'
),
numbered AS (
    SELECT e.*,
           COALESCE((SELECT MAX(s.folio_sequence)
                      FROM client_company_loan s
                      WHERE s.company_id = e.company_id
                        AND s.folio_group_code = 'S/E'), 0)
           + ROW_NUMBER() OVER (
               PARTITION BY e.company_id ORDER BY e.created_at NULLS LAST, e.id
             ) AS new_sequence
    FROM eligible e
    WHERE e.pay_day BETWEEN 1 AND 14
)
SELECT id, company_id, old_folio_number, old_group_code, old_sequence,
       pay_day, new_sequence::integer AS new_sequence,
       'BFS-S/E-' || LPAD(new_sequence::text, 5, '0') AS new_folio_number
FROM numbered;

-- A prior partial operation or unexpected existing number must never be overwritten.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM bfs_se_folio_changes c
    JOIN client_company_loan l ON l.company_id = c.company_id
       AND l.folio_number = c.new_folio_number AND l.id <> c.id
  ) THEN
    RAISE EXCEPTION 'Conflicting destination folio number: correction aborted';
  END IF;
  IF EXISTS (
    SELECT 1 FROM bfs_se_folio_changes c
    JOIN bfs_folio_group_correction_audit a ON a.loan_id = c.id
  ) THEN
    RAISE EXCEPTION 'Previously audited loan is not in S/E: correction aborted';
  END IF;
END $$;

INSERT INTO bfs_folio_group_correction_audit
  (loan_id, company_id, old_folio_number, new_folio_number,
   old_group_code, old_sequence, new_sequence, contractual_pay_day)
SELECT id, company_id, old_folio_number, new_folio_number,
       old_group_code, old_sequence, new_sequence, pay_day
FROM bfs_se_folio_changes;

UPDATE client_company_loan l
SET folio_group_code = 'S/E',
    folio_sequence = c.new_sequence,
    folio_number = c.new_folio_number
FROM bfs_se_folio_changes c
WHERE l.id = c.id AND l.company_id = c.company_id;

-- Check all expected rows were changed before committing.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM bfs_se_folio_changes c
    JOIN client_company_loan l ON l.id = c.id
    WHERE l.folio_group_code <> 'S/E'
       OR l.folio_sequence <> c.new_sequence
       OR l.folio_number <> c.new_folio_number
  ) THEN
    RAISE EXCEPTION 'BFS folio correction validation failed; transaction rolled back';
  END IF;
END $$;
COMMIT;

-- Review after commit:
-- SELECT * FROM bfs_folio_group_correction_audit ORDER BY corrected_at, loan_id;
