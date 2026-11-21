-- Drill down on the two small legacy opening-vs-installment differences.
-- Compare loan-level inferred opening amount to installment-level paid amounts.
-- No changes to settlements, repayments, calculator or production records.
BEGIN READ ONLY;
WITH target(loan_id) AS (VALUES
 ('281b2206-536f-483c-8dab-5125a532d2b2'::uuid),
 ('bcaf1cd0-5747-4e37-861b-e0552d79e5df'::uuid)
)
SELECT l.loan_reference,l.id AS loan_id,l.amount_paid::numeric(18,2) AS loan_amount_paid,
       ri.id AS installment_id,ri.installment_number,ri.status AS installment_status,
       ri.is_superseded,ri.paid_amount::numeric(18,2) AS installment_paid,
       l.calculation_breakdown AS migration_calculation_breakdown
FROM target t JOIN client_company_loan l ON l.id=t.loan_id
LEFT JOIN repayment_installments ri ON ri.loan_id=l.id
ORDER BY l.loan_reference,ri.is_superseded,ri.installment_number;
COMMIT;
