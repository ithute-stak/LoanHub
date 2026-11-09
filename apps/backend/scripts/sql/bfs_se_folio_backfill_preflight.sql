-- READ ONLY. Run against a verified restored production snapshot before backfill.
-- Produces candidate counts, group breakdown, and duplicate/conflict observations.
-- No loan or audit records are modified.
BEGIN TRANSACTION READ ONLY;
WITH eligible AS (
    SELECT l.id, l.company_id, l.folio_number, l.folio_group_code,
           l.folio_sequence, l.created_at,
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
    FROM client_company_loan l WHERE l.folio_company_code = 'BFS'
),
candidates AS (
    SELECT * FROM eligible
    WHERE pay_day BETWEEN 1 AND 14 AND folio_group_code <> 'S/E'
)
SELECT company_id, folio_group_code AS previous_group,
       COUNT(*) AS loans_to_move,
       MIN(pay_day) AS lowest_payment_day,
       MAX(pay_day) AS highest_payment_day
FROM candidates
GROUP BY company_id, folio_group_code
ORDER BY company_id, previous_group;

SELECT l.company_id, l.folio_group_code,
       COUNT(*) AS current_loans,
       MAX(l.folio_sequence) AS highest_sequence,
       COUNT(*) - COUNT(DISTINCT l.folio_sequence) AS duplicate_sequences
FROM client_company_loan l
WHERE l.folio_company_code = 'BFS'
GROUP BY l.company_id, l.folio_group_code
ORDER BY l.company_id, l.folio_group_code;

SELECT l.company_id, l.folio_number, COUNT(*) AS duplicated
FROM client_company_loan l
WHERE l.folio_company_code = 'BFS'
GROUP BY l.company_id, l.folio_number
HAVING COUNT(*) > 1;
COMMIT;
