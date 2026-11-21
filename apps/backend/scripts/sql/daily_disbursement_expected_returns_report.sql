-- Read-only daily disbursement and expected contractual repayment report.
-- Parameters: :company_id (required UUID), :start_date and :end_date (inclusive dates),
--             :branch_id (optional UUID; NULL means all authorized branches).
-- Execute only after tenant/branch authorization is enforced by the caller.
-- Dates follow the database session timezone; set the tenant reporting timezone explicitly.
-- This is a CURRENT contractual snapshot, not an origination-time immutable ledger.
-- total_repayable may change after settlement, reversal, renewal or restructuring.
-- Top-up principal may include refinanced amounts, so principal is not always cash out.
WITH issued AS (
    SELECT
        l.disbursed_at::date AS issue_date,
        l.id,
        l.principal_amount,
        l.total_repayable,
        l.processing_fee,
        l.is_top_up,
        l.top_up_cash_amount
    FROM client_company_loan AS l
    WHERE l.company_id = CAST(:company_id AS uuid)
      AND l.disbursed_at IS NOT NULL
      AND l.disbursed_at >= CAST(:start_date AS date)
      AND l.disbursed_at < CAST(:end_date AS date) + INTERVAL '1 day'
      AND (CAST(:branch_id AS uuid) IS NULL OR l.branch_id = CAST(:branch_id AS uuid))
      AND l.status::text NOT IN ('cancelled', 'rejected')
)
SELECT
    issue_date,
    COUNT(*) AS loans_issued,
    COALESCE(SUM(principal_amount), 0)::numeric(15,2) AS principal_issued,
    COALESCE(SUM(CASE WHEN is_top_up THEN top_up_cash_amount ELSE principal_amount END), 0)::numeric(15,2) AS indicative_cash_issued,
    COALESCE(SUM(total_repayable), 0)::numeric(15,2) AS expected_contractual_return,
    COALESCE(SUM(total_repayable - principal_amount), 0)::numeric(15,2) AS expected_return_above_principal,
    COUNT(*) FILTER (WHERE is_top_up) AS top_up_loans
FROM issued
GROUP BY issue_date
ORDER BY issue_date DESC;
