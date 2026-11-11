-- LoanHub incident: loan status integrity monitor (human review only).
-- All work is confined to a repeatable-read, read-only transaction.
-- Execute only inside a trusted operator session with a SELECT-only DB role.
-- Do NOT publish row-level results to GitHub Actions logs.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '30s';

WITH payment_summary AS (
  SELECT loan_id,
    COALESCE(SUM(amount) FILTER (
      WHERE direction::text='INBOUND' AND status::text='SUCCEEDED'
        AND purpose::text='LOAN_REPAYMENT'
    ),0) AS successful_repayments,
    COUNT(*) FILTER (
      WHERE direction::text='INBOUND' AND status::text='SUCCEEDED'
        AND purpose::text='LOAN_REPAYMENT'
    ) AS successful_repayment_count
  FROM payment_transactions
  WHERE loan_id IS NOT NULL
  GROUP BY loan_id
),
loan_flags AS (
  SELECT l.id, l.loan_reference, l.company_id, l.borrower_id,
    l.status::text AS stored_status, l.balance, l.amount_paid, l.total_repayable,
    EXISTS (SELECT 1 FROM legacy_loan_captures lc WHERE lc.loan_id=l.id) AS legacy_linked,
    EXISTS (SELECT 1 FROM loan_top_up_settlements t
            WHERE t.parent_loan_id=l.id AND t.status='settled') AS topup_parent_settled,
    COALESCE(ps.successful_repayments,0) AS successful_repayments,
    COALESCE(ps.successful_repayment_count,0) AS successful_repayment_count,
    EXISTS (SELECT 1 FROM repayment_installments ri
            WHERE ri.loan_id=l.id
              AND NOT ri.is_superseded
              AND ri.superseded_by_cycle_id IS NULL
              AND ri.status::text NOT IN ('WAIVED','PAID')
              AND ri.total_due > ri.paid_amount+0.01) AS has_unpaid_current_installments,
    EXISTS (SELECT 1 FROM client_company_loan newer
            WHERE newer.parent_loan_id=l.id AND newer.company_id=l.company_id
              AND newer.borrower_id=l.borrower_id) AS has_linked_child
  FROM client_company_loan l
  LEFT JOIN payment_summary ps ON ps.loan_id=l.id
),
review_flags AS (
  SELECT *,
    CASE
      WHEN balance < -0.01 THEN 'NEGATIVE_BALANCE'
      WHEN amount_paid < -0.01 THEN 'NEGATIVE_PAID'
      WHEN stored_status='completed' AND balance > 0.01
        THEN 'COMPLETED_POSITIVE_BALANCE'
      WHEN stored_status IN ('active','defaulted') AND balance <= 0.01
        THEN 'OPEN_LOAN_ZERO_BALANCE'
      WHEN stored_status='completed' AND amount_paid+0.01<total_repayable
        AND NOT legacy_linked AND NOT topup_parent_settled
        AND NOT (calculated_early_settlement)
        THEN 'COMPLETED_UNDERPAID_WITHOUT_SETTLEMENT_EVIDENCE'
      ELSE NULL
    END AS review_reason
  FROM (
    SELECT f.*,
      EXISTS (
        SELECT 1 FROM payment_transactions p
        WHERE p.loan_id=f.id AND p.provider_payload ? 'early_settlement_id'
          AND p.status::text='SUCCEEDED'
      ) AS calculated_early_settlement
    FROM loan_flags f
  ) x
)
SELECT review_reason, COUNT(*) AS affected_loans
FROM review_flags
WHERE review_reason IS NOT NULL
GROUP BY review_reason
ORDER BY review_reason;

-- Row-level review list. No national ID, name, telephone or bank information.
WITH payment_summary AS (
  SELECT loan_id,
    COALESCE(SUM(amount) FILTER (
      WHERE direction::text='INBOUND' AND status::text='SUCCEEDED'
        AND purpose::text='LOAN_REPAYMENT'
    ),0) AS successful_repayments
  FROM payment_transactions WHERE loan_id IS NOT NULL GROUP BY loan_id
)
SELECT l.loan_reference, l.status::text AS stored_status,
       l.total_repayable, l.amount_paid, l.balance,
       COALESCE(ps.successful_repayments,0) AS posted_repayments,
       EXISTS(SELECT 1 FROM legacy_loan_captures lc WHERE lc.loan_id=l.id) AS legacy_capture,
       EXISTS(SELECT 1 FROM loan_top_up_settlements t
              WHERE t.parent_loan_id=l.id AND t.status='settled') AS settled_by_topup,
       EXISTS(SELECT 1 FROM payment_transactions p WHERE p.loan_id=l.id
              AND p.status::text='SUCCEEDED'
              AND p.provider_payload ? 'early_settlement_id') AS early_settlement_payment
FROM client_company_loan l
LEFT JOIN payment_summary ps ON ps.loan_id=l.id
WHERE (l.status::text='completed' AND l.balance>0.01)
   OR (l.status::text IN ('active','defaulted') AND l.balance<=0.01)
   OR (l.status::text='completed' AND l.amount_paid+0.01<l.total_repayable
       AND NOT EXISTS(SELECT 1 FROM legacy_loan_captures lc WHERE lc.loan_id=l.id)
       AND NOT EXISTS(SELECT 1 FROM loan_top_up_settlements t
                      WHERE t.parent_loan_id=l.id AND t.status='settled')
       AND NOT EXISTS(SELECT 1 FROM payment_transactions p WHERE p.loan_id=l.id
                      AND p.status::text='SUCCEEDED'
                      AND p.provider_payload ? 'early_settlement_id'))
ORDER BY l.loan_reference;

ROLLBACK;
