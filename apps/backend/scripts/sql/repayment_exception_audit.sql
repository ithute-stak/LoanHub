-- LoanHub repayment exception audit (READ ONLY)
-- Run with psql -X -v ON_ERROR_STOP=1 -f <this-file>.
-- Does not certify receipt of physical cash or authorize Principal x% posting.
-- Every section is scoped to a tenant and loan; never add payment and cash totals.
BEGIN READ ONLY;

-- Successful inbound repayments lacking any installment allocation.
-- Includes legacy cash-out loans; missing allocations are exceptions for review,
-- not automatic evidence of missing cash.
SELECT
    pt.company_id,
    pt.loan_id,
    COUNT(*) AS unallocated_payment_count,
    SUM(pt.amount) AS unallocated_payment_amount
FROM payment_transactions pt
WHERE pt.status = 'SUCCEEDED'
  AND pt.purpose = 'LOAN_REPAYMENT'
  AND pt.direction = 'INBOUND'
  AND NOT EXISTS (
      SELECT 1
      FROM payment_allocations pa
      WHERE pa.payment_id = pt.id
  )
GROUP BY pt.company_id, pt.loan_id
ORDER BY pt.company_id, pt.loan_id;

-- Historical opening amounts explicitly captured in completed legacy settlements.
-- This is a separate category, not an installment-allocation discrepancy.
-- A recorded snapshot is NOT independent proof of historical collection.
SELECT
    s.company_id,
    s.loan_id,
    l.origination_channel,
    l.calculation_breakdown->>'source' AS origination_source,
    s.original_amount_paid,
    s.calculation_snapshot->>'live_ledger_received' AS ledger_at_quote,
    s.calculation_snapshot->>'historical_opening_amount' AS historical_opening_amount
FROM loan_early_settlements s
JOIN client_company_loan l
  ON l.id = s.loan_id
 AND l.company_id = s.company_id
WHERE s.status = 'settled'
  AND s.reversed_at IS NULL
  AND COALESCE(
    (s.calculation_snapshot->>'historical_opening_amount')::numeric, 0
  ) > 0
ORDER BY s.company_id, s.loan_id;

-- Reconciliation control totals. These are separate categories and MUST NOT be added
-- together as cash received: historical openings may predate the live ledger.
WITH unallocated AS (
    SELECT pt.id, pt.amount
    FROM payment_transactions pt
    WHERE pt.status = 'SUCCEEDED'
      AND pt.purpose = 'LOAN_REPAYMENT'
      AND pt.direction = 'INBOUND'
      AND NOT EXISTS (
          SELECT 1 FROM payment_allocations pa WHERE pa.payment_id = pt.id
      )
), historical AS (
    SELECT s.loan_id, s.company_id,
           (s.calculation_snapshot->>'historical_opening_amount')::numeric AS amount
    FROM loan_early_settlements s
    JOIN client_company_loan l ON l.id = s.loan_id AND l.company_id = s.company_id
    WHERE s.status = 'settled'
      AND s.reversed_at IS NULL
      AND COALESCE((s.calculation_snapshot->>'historical_opening_amount')::numeric, 0) > 0
)
SELECT 'unallocated_repayments' AS exception_category,
       COUNT(*) AS record_count,
       COALESCE(SUM(amount), 0)::numeric(18,2) AS amount_maloti
FROM unallocated
UNION ALL
SELECT 'settled_historical_openings' AS exception_category,
       COUNT(*) AS record_count,
       COALESCE(SUM(amount), 0)::numeric(18,2) AS amount_maloti
FROM historical;

COMMIT;
