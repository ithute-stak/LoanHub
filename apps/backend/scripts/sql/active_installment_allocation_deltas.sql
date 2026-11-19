-- LoanHub installment paid-vs-allocation classification (READ ONLY).
-- Historical migration balances are not necessarily represented by live allocations.
-- Classification is evidence triage, NOT financial certification or permission to backfill.
BEGIN READ ONLY;
CREATE TEMP VIEW installment_delta_triage AS
WITH allocations AS (
 SELECT installment_id, COUNT(*) AS allocation_count,
        SUM(amount)::numeric(18,2) AS allocated_amount
 FROM payment_allocations GROUP BY installment_id
), live_payments AS (
 SELECT company_id,loan_id,COUNT(*) AS successful_payment_count,
        SUM(amount)::numeric(18,2) AS successful_payment_amount
 FROM payment_transactions
 WHERE status='SUCCEEDED' AND purpose='LOAN_REPAYMENT' AND direction='INBOUND'
 GROUP BY company_id,loan_id
), differences AS (
 SELECT l.company_id,l.id AS loan_id,l.loan_reference,
        l.origination_channel,l.calculation_breakdown->>'source' AS origination_source,
        ri.id AS installment_id,ri.installment_number,ri.is_superseded,
        ri.paid_amount::numeric(18,2) AS recorded_paid,
        COALESCE(a.allocated_amount,0)::numeric(18,2) AS allocated_paid,
        COALESCE(a.allocation_count,0) AS allocation_count,
        (ri.paid_amount-COALESCE(a.allocated_amount,0))::numeric(18,2) AS difference,
        COALESCE(p.successful_payment_count,0) AS successful_payment_count,
        COALESCE(p.successful_payment_amount,0)::numeric(18,2) AS successful_payment_amount
 FROM repayment_installments ri
 JOIN client_company_loan l ON l.id=ri.loan_id
 LEFT JOIN allocations a ON a.installment_id=ri.id
 LEFT JOIN live_payments p ON p.company_id=l.company_id AND p.loan_id=l.id
 WHERE ri.is_superseded=FALSE
)
SELECT *, CASE
 WHEN origination_channel='legacy_cashout' OR origination_source='legacy_cashout_book'
 THEN CASE WHEN successful_payment_count>0 OR allocation_count>0
           THEN 'legacy_mixed_live_evidence_review'
           ELSE 'legacy_opening_balance_candidate' END
 WHEN loan_reference LIKE 'LEG-%' THEN 'legacy_reference_unverified_origin'
 ELSE 'nonlegacy_installment_difference_review' END AS review_category
FROM differences WHERE difference<>0;

-- Summary is the control total; do not treat the difference as missing cash.
SELECT review_category,COUNT(*) AS installment_count,
       COUNT(DISTINCT loan_id) AS loan_count,
       SUM(difference)::numeric(18,2) AS net_difference,
       SUM(ABS(difference))::numeric(18,2) AS absolute_difference
FROM installment_delta_triage GROUP BY review_category ORDER BY review_category;

-- Individual cases requiring further investigation, including any legacy loan
-- with post-migration payments or installment allocations.
SELECT company_id,loan_id,loan_reference,origination_channel,origination_source,
       installment_id,installment_number,recorded_paid,allocated_paid,
       difference,allocation_count,successful_payment_count,successful_payment_amount,
       review_category
FROM installment_delta_triage
WHERE review_category<>'legacy_opening_balance_candidate'
ORDER BY review_category,loan_id,installment_number;

-- Total cross-check of the same discrepancy population.
SELECT COUNT(*) AS affected_installments,COUNT(DISTINCT loan_id) AS affected_loans,
       COALESCE(SUM(difference),0)::numeric(18,2) AS net_difference,
       COALESCE(SUM(ABS(difference)),0)::numeric(18,2) AS absolute_difference
FROM installment_delta_triage;
DROP VIEW installment_delta_triage;
COMMIT;
