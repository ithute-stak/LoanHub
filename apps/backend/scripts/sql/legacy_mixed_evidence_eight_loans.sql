-- Eight mixed-evidence legacy loans identified in production on 2026-11-19.
-- Read only: compare migration-paid installments, live allocations, and payments.
-- This is NOT an instruction to backfill historical allocations.
BEGIN READ ONLY;
WITH target(loan_id) AS (VALUES
 ('281b2206-536f-483c-8dab-5125a532d2b2'::uuid),
 ('35394f4d-0411-4551-8655-e0c4b73a6aa5'::uuid),
 ('42f90f36-95c4-41b4-803e-f33db18e'::uuid),
 ('56de3a68-7e80-4638-aadd-e8be46b2624c'::uuid),
 ('7b5060ae-7f6a-4c98-bb39-8c1f19633bcb'::uuid),
 ('9ea5fbde-561c-45c0-9072-55eb9c6dc2b2'::uuid),
 ('bcaf1cd0-5747-4e37-861b-e0552d79e5df'::uuid),
 ('cb381bf3-0ff1-4763-9523-ffed3702cd1f'::uuid)
), installments AS (
 SELECT ri.loan_id,COUNT(*) FILTER (WHERE NOT ri.is_superseded) AS active_installment_count,
        COALESCE(SUM(ri.paid_amount) FILTER (WHERE NOT ri.is_superseded),0)::numeric(18,2) AS active_recorded_paid
 FROM repayment_installments ri JOIN target t ON t.loan_id=ri.loan_id GROUP BY ri.loan_id
), allocations AS (
 SELECT ri.loan_id,COUNT(pa.id) FILTER (WHERE NOT ri.is_superseded) AS active_allocation_count,
        COALESCE(SUM(pa.amount) FILTER (WHERE NOT ri.is_superseded),0)::numeric(18,2) AS active_allocated_paid
 FROM repayment_installments ri JOIN target t ON t.loan_id=ri.loan_id
 LEFT JOIN payment_allocations pa ON pa.installment_id=ri.id GROUP BY ri.loan_id
), payments AS (
 SELECT pt.loan_id,COUNT(*) AS successful_repayments,
        SUM(pt.amount)::numeric(18,2) AS successful_repayment_amount,
        COUNT(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM payment_allocations pa WHERE pa.payment_id=pt.id)) AS unallocated_repayments
 FROM payment_transactions pt JOIN target t ON t.loan_id=pt.loan_id
 WHERE pt.status='SUCCEEDED' AND pt.purpose='LOAN_REPAYMENT' AND pt.direction='INBOUND'
 GROUP BY pt.loan_id
), settlements AS (
 SELECT s.loan_id,COUNT(*) AS completed_settlements
 FROM loan_early_settlements s JOIN target t ON t.loan_id=s.loan_id
 WHERE s.status='settled' AND s.reversed_at IS NULL GROUP BY s.loan_id
)
SELECT l.company_id,l.id AS loan_id,l.loan_reference,l.status AS loan_status,
       l.origination_channel,l.calculation_breakdown->>'source' AS origination_source,
       l.amount_paid AS loan_amount_paid,l.balance AS loan_balance,
       COALESCE(i.active_installment_count,0) AS active_installment_count,
       COALESCE(i.active_recorded_paid,0) AS active_recorded_paid,
       COALESCE(a.active_allocation_count,0) AS active_allocation_count,
       COALESCE(a.active_allocated_paid,0) AS active_allocated_paid,
       (COALESCE(i.active_recorded_paid,0)-COALESCE(a.active_allocated_paid,0))::numeric(18,2) AS active_paid_allocation_gap,
       COALESCE(p.successful_repayments,0) AS successful_repayments,
       COALESCE(p.successful_repayment_amount,0) AS successful_repayment_amount,
       COALESCE(p.unallocated_repayments,0) AS unallocated_repayments,
       COALESCE(s.completed_settlements,0) AS completed_settlements
FROM target t JOIN client_company_loan l ON l.id=t.loan_id
LEFT JOIN installments i ON i.loan_id=l.id
LEFT JOIN allocations a ON a.loan_id=l.id
LEFT JOIN payments p ON p.loan_id=l.id
LEFT JOIN settlements s ON s.loan_id=l.id
ORDER BY l.loan_reference;
COMMIT;
