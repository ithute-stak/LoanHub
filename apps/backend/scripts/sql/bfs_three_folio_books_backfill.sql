-- BFS canonical folio correction: Force=15-22, CIVIL=23-26, S/E=27-31 or 1-14.
-- CAUTION: This changes folio identifiers used in historic signed documents.
-- Execute only after verified backup/restore, document review, and approved downtime.
-- Run this SQL on a restored production snapshot first. Do not run automatically.
BEGIN;
SET LOCAL lock_timeout = '15s';
SET LOCAL statement_timeout = '5min';
LOCK TABLE client_company_loan IN SHARE ROW EXCLUSIVE MODE;

-- Shares the existing historical-folio audit contract/lookup introduced in #663.
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

CREATE TEMP TABLE bfs_canonical_changes ON COMMIT DROP AS
WITH source AS (
    SELECT l.id, l.company_id, l.created_at, l.folio_number AS old_folio_number,
           l.folio_group_code AS old_group_code, l.folio_sequence AS old_sequence,
           l.folio_company_code,
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
),
classified AS (
    SELECT *, CASE
        WHEN pay_day BETWEEN 15 AND 22 THEN 'Force'
        WHEN pay_day BETWEEN 23 AND 26 THEN 'CIVIL'
        WHEN pay_day BETWEEN 27 AND 31 OR pay_day BETWEEN 1 AND 14 THEN 'S/E'
        ELSE NULL
    END AS new_group
    FROM source
),
candidates AS (
    SELECT * FROM classified
    WHERE new_group IS DISTINCT FROM old_group_code
),
numbered AS (
    SELECT c.*,
           COALESCE((
               SELECT MAX(l.folio_sequence)
               FROM client_company_loan l
               WHERE l.company_id = c.company_id AND l.folio_group_code = c.new_group
           ), 0)
           + ROW_NUMBER() OVER (
               PARTITION BY c.company_id, c.new_group
               ORDER BY c.created_at NULLS LAST, c.id
           ) AS new_sequence
    FROM candidates c
    WHERE c.new_group IS NOT NULL
)
SELECT id, company_id, old_folio_number, old_group_code, old_sequence,
       pay_day, new_group, new_sequence::integer AS new_sequence,
       ('BFS-' || new_group || '-' || LPAD(new_sequence::text, 5, '0')) AS new_folio_number
FROM numbered;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM client_company_loan l
    WHERE l.folio_company_code = 'BFS'
      AND COALESCE(
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
      ) NOT BETWEEN 1 AND 31
      OR l.folio_company_code = 'BFS' AND (
        l.preferred_payment_day IS NULL AND l.first_payment_due IS NULL
        AND (l.calculation_breakdown #>> '{schedule_rows,0,due_date}') IS NULL
        AND (l.calculation_breakdown #>> '{due_dates,0}') IS NULL
      )
  ) THEN
    RAISE EXCEPTION 'BFS loans with missing or invalid pay day: no changes applied';
  END IF;
  IF EXISTS (
    SELECT 1 FROM bfs_canonical_changes c
    JOIN bfs_folio_group_correction_audit a ON a.loan_id = c.id
  ) THEN
    RAISE EXCEPTION 'Previously corrected loan still misclassified: investigate before retry';
  END IF;
  IF EXISTS (
    SELECT 1 FROM bfs_canonical_changes c
    JOIN client_company_loan l
      ON l.company_id = c.company_id AND l.folio_number = c.new_folio_number
     AND l.id <> c.id
  ) THEN
    RAISE EXCEPTION 'New folio number collides with an existing loan';
  END IF;
  IF EXISTS (
    SELECT 1 FROM bfs_canonical_changes c
    JOIN bfs_folio_group_correction_audit a
      ON a.company_id = c.company_id AND a.old_folio_number = c.new_folio_number
  ) THEN
    RAISE EXCEPTION 'New folio number collides with a historical folio alias';
  END IF;
END $$;

INSERT INTO bfs_folio_group_correction_audit
    (loan_id, company_id, old_folio_number, new_folio_number, old_group_code,
     new_group_code, old_sequence, new_sequence, contractual_pay_day)
SELECT id, company_id, old_folio_number, new_folio_number, old_group_code,
       new_group, old_sequence, new_sequence, pay_day
FROM bfs_canonical_changes;

UPDATE client_company_loan l
SET folio_group_code = c.new_group,
    folio_sequence = c.new_sequence,
    folio_number = c.new_folio_number
FROM bfs_canonical_changes c
WHERE l.id = c.id AND l.company_id = c.company_id;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM bfs_canonical_changes c
    JOIN client_company_loan l ON l.id = c.id
    WHERE l.folio_group_code <> c.new_group
       OR l.folio_sequence <> c.new_sequence
       OR l.folio_number <> c.new_folio_number
  ) THEN
    RAISE EXCEPTION 'Backfill verification failed; transaction rolled back';
  END IF;
  IF EXISTS (
    SELECT 1 FROM client_company_loan l
    WHERE l.folio_company_code = 'BFS'
      AND l.folio_group_code NOT IN ('Force', 'CIVIL', 'S/E')
  ) THEN
    RAISE EXCEPTION 'Legacy BFS group remains; transaction rolled back';
  END IF;
END $$;
COMMIT;

-- Post-run verification:
-- SELECT folio_group_code, count(*) FROM client_company_loan
-- WHERE folio_company_code='BFS' GROUP BY folio_group_code ORDER BY 1;
-- SELECT count(*) FROM bfs_folio_group_correction_audit;
