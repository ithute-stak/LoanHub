-- Read-only audit of active installment paid amounts versus linked allocations.
-- A discrepancy is not permission to rewrite completed settlement accounting.
BEGIN READ ONLY;
WITH allocation_totals AS (
 SELECT pa.installment_id,COUNT(*) AS allocation_count,
        COALESCE(SUM(pa.amount),0)::numeric(18,2) AS allocated_amount
 FROM payment_allocations pa GROUP BY pa.installment_id
), active_installments AS (
 SELECT l.company_id,l.id AS loan_id,l.loan_reference,l.status AS loan_status,
        ri.id AS installment_id,ri.installment_number,ri.status AS installment_status,
        ri.paid_amount::numeric(18,2) AS recorded_paid,
        COALESCE(a.allocated_amount,0)::numeric(18,2) AS allocated_paid,
        COALESCE(a.allocation_count,0) AS allocation_count,
        (ri.paid_amount-COALESCE(a.allocated_amount,0))::numeric(18,2) AS difference
 FROM repayment_installments ri
 JOIN client_company_loan l ON l.id=ri.loan_id
 LEFT JOIN allocation_totals a ON a.installment_id=ri.id
 WHERE ri.is_superseded=FALSE
), exceptions AS (
 SELECT * FROM active_installments WHERE difference<>0
)
SELECT company_id,loan_id,loan_reference,loan_status,installment_id,
       installment_number,installment_status,recorded_paid,allocated_paid,
       allocation_count,difference
FROM exceptions ORDER BY company_id,loan_id,installment_number;

WITH allocation_totals AS (
 SELECT installment_id,COALESCE(SUM(amount),0) AS allocated_amount
 FROM payment_allocations GROUP BY installment_id
), exceptions AS (
 SELECT ri.id,ri.loan_id,
        (ri.paid_amount-COALESCE(a.allocated_amount,0))::numeric(18,2) AS difference
 FROM repayment_installments ri
 LEFT JOIN allocation_totals a ON a.installment_id=ri.id
 WHERE ri.is_superseded=FALSE
 AND ri.paid_amount IS DISTINCT FROM COALESCE(a.allocated_amount,0)
)
SELECT COUNT(*) AS affected_installments,COUNT(DISTINCT loan_id) AS affected_loans,
       COALESCE(SUM(difference),0)::numeric(18,2) AS net_difference,
       COALESCE(SUM(ABS(difference)),0)::numeric(18,2) AS absolute_difference
FROM exceptions;
COMMIT;
