-- LoanHub repayment allocation triage (READ ONLY).
-- Identify missing allocation evidence without writing financial records.
-- This report does not authorize creating allocations or modifying settled loans.
BEGIN READ ONLY;

WITH missing AS (
    SELECT pt.company_id, pt.loan_id, pt.id AS payment_id, pt.amount
    FROM payment_transactions pt
    WHERE pt.status = 'SUCCEEDED'
      AND pt.purpose = 'LOAN_REPAYMENT'
      AND pt.direction = 'INBOUND'
      AND NOT EXISTS (
          SELECT 1 FROM payment_allocations pa WHERE pa.payment_id = pt.id
      )
), settlement AS (
    SELECT DISTINCT s.company_id, s.loan_id
    FROM loan_early_settlements s
    WHERE s.status = 'settled' AND s.reversed_at IS NULL
), classified AS (
    SELECT m.company_id, m.loan_id,
           COUNT(*) AS payment_count,
           SUM(m.amount)::numeric(18,2) AS unallocated_amount,
           CASE
             WHEN l.origination_channel = 'legacy_cashout'
              AND l.calculation_breakdown->>'source' = 'legacy_cashout_book'
              AND s.loan_id IS NOT NULL
               THEN 'legacy_cashout_settled_review'
             WHEN s.loan_id IS NOT NULL THEN 'settled_nonlegacy_review'
             ELSE 'other_unallocated_review'
           END AS review_category
    FROM missing m
    JOIN client_company_loan l
      ON l.company_id = m.company_id AND l.id = m.loan_id
    LEFT JOIN settlement s
      ON s.company_id = m.company_id AND s.loan_id = m.loan_id
    GROUP BY m.company_id, m.loan_id, l.origination_channel,
             l.calculation_breakdown->>'source', s.loan_id
)
SELECT company_id, loan_id, review_category, payment_count, unallocated_amount
FROM classified
ORDER BY review_category, company_id, loan_id;

WITH missing AS (
    SELECT pt.company_id, pt.loan_id, pt.id AS payment_id, pt.amount
    FROM payment_transactions pt
    WHERE pt.status = 'SUCCEEDED'
      AND pt.purpose = 'LOAN_REPAYMENT'
      AND pt.direction = 'INBOUND'
      AND NOT EXISTS (SELECT 1 FROM payment_allocations pa WHERE pa.payment_id = pt.id)
), settlement AS (
    SELECT DISTINCT company_id, loan_id
    FROM loan_early_settlements
    WHERE status = 'settled' AND reversed_at IS NULL
), classified AS (
    SELECT m.company_id, m.loan_id, m.payment_id, m.amount,
           CASE
             WHEN l.origination_channel = 'legacy_cashout'
              AND l.calculation_breakdown->>'source' = 'legacy_cashout_book'
              AND s.loan_id IS NOT NULL THEN 'legacy_cashout_settled_review'
             WHEN s.loan_id IS NOT NULL THEN 'settled_nonlegacy_review'
             ELSE 'other_unallocated_review'
           END AS review_category
    FROM missing m
    JOIN client_company_loan l ON l.company_id=m.company_id AND l.id=m.loan_id
    LEFT JOIN settlement s ON s.company_id=m.company_id AND s.loan_id=m.loan_id
)
SELECT review_category, COUNT(DISTINCT loan_id) AS loan_count,
       COUNT(*) AS payment_count,
       COALESCE(SUM(amount),0)::numeric(18,2) AS amount_maloti
FROM classified
GROUP BY review_category
ORDER BY review_category;
COMMIT;
