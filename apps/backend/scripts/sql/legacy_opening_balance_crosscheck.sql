-- Historical opening balance reconciliation for eight legacy loans.
-- Differences are investigative signals, never instructions to update financial data.
BEGIN READ ONLY;
WITH target(loan_id) AS (VALUES
 ('281b2206-536f-483c-8dab-5125a532d2b2'::uuid),
 ('35394f4d-0411-4551-8655-e0c4b73a6aa5'::uuid),
 ('42f90f36-95c4-41b4-803e-5fe3f33db18e'::uuid),
 ('56de3a68-7e80-4638-aadd-e8be46b2624c'::uuid),
 ('7b5060ae-7f6a-4c98-bb39-8c1f19633bcb'::uuid),
 ('9ea5fbde-561c-45c0-9072-55eb9c6dc2b2'::uuid),
 ('bcaf1cd0-5747-4e37-861b-e0552d79e5df'::uuid),
 ('cb381bf3-0ff1-4763-9523-ffed3702cd1f'::uuid)
),
paid AS (
 SELECT ri.loan_id,
 COALESCE(SUM(ri.paid_amount) FILTER (WHERE NOT ri.is_superseded),0)::numeric(18,2) AS active_installment_paid
 FROM repayment_installments ri JOIN target t ON t.loan_id=ri.loan_id GROUP BY ri.loan_id
),
allocations AS (
 SELECT ri.loan_id,
 COALESCE(SUM(pa.amount) FILTER (WHERE NOT ri.is_superseded),0)::numeric(18,2) AS active_allocated
 FROM repayment_installments ri JOIN target t ON t.loan_id=ri.loan_id
 LEFT JOIN payment_allocations pa ON pa.installment_id=ri.id GROUP BY ri.loan_id
),
live AS (
 SELECT pt.loan_id,COALESCE(SUM(pt.amount),0)::numeric(18,2) AS successful_live_paid
 FROM payment_transactions pt JOIN target t ON t.loan_id=pt.loan_id
 WHERE pt.status='SUCCEEDED' AND pt.purpose='LOAN_REPAYMENT' AND pt.direction='INBOUND'
 GROUP BY pt.loan_id
)
SELECT l.loan_reference,l.status AS loan_status,
 l.amount_paid::numeric(18,2) AS loan_amount_paid,
 COALESCE(v.successful_live_paid,0) AS successful_live_paid,
 (l.amount_paid-COALESCE(v.successful_live_paid,0))::numeric(18,2) AS inferred_historical_paid,
 COALESCE(p.active_installment_paid,0) AS active_installment_paid,
 COALESCE(a.active_allocated,0) AS active_allocated,
 (COALESCE(p.active_installment_paid,0)-COALESCE(a.active_allocated,0))::numeric(18,2) AS installment_gap,
 ((l.amount_paid-COALESCE(v.successful_live_paid,0))-
 (COALESCE(p.active_installment_paid,0)-COALESCE(a.active_allocated,0)))::numeric(18,2) AS opening_vs_installment_difference,
 l.calculation_breakdown->>'source' AS migration_source
FROM target t JOIN client_company_loan l ON l.id=t.loan_id
LEFT JOIN paid p ON p.loan_id=l.id
LEFT JOIN allocations a ON a.loan_id=l.id
LEFT JOIN live v ON v.loan_id=l.id
ORDER BY l.loan_reference;
COMMIT;
