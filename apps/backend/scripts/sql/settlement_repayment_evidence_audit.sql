-- Settlement repayment evidence audit (READ ONLY).
-- Tests explicit settlement->payment linkage and internal cash evidence.
-- No conclusion about independent physical cash receipt or historical source documents.
BEGIN READ ONLY;
WITH missing_allocations AS (
 SELECT pt.company_id,pt.loan_id,pt.id AS payment_id,pt.amount
 FROM payment_transactions pt
 WHERE pt.status='SUCCEEDED' AND pt.purpose='LOAN_REPAYMENT'
 AND pt.direction='INBOUND'
 AND NOT EXISTS (SELECT 1 FROM payment_allocations pa WHERE pa.payment_id=pt.id)
), evidence AS (
 SELECT m.company_id,m.loan_id,m.payment_id,m.amount,
        l.origination_channel,
        s.payment_id AS settlement_payment_id,s.settlement_amount,
        s.status AS settlement_status,
        ct.payment_id AS cash_payment_id,ct.applied_amount AS cash_applied_amount,
        ct.direction AS cash_direction,
        CASE WHEN s.payment_id IS NULL THEN 'missing_settlement_payment_link'
             WHEN s.payment_id <> m.payment_id THEN 'settlement_payment_mismatch'
             WHEN s.settlement_amount IS DISTINCT FROM m.amount THEN 'settlement_amount_mismatch'
             WHEN ct.payment_id IS NULL THEN 'missing_cash_evidence'
             WHEN ct.direction::text <> 'INBOUND' THEN 'cash_direction_mismatch'
             WHEN ct.applied_amount IS DISTINCT FROM m.amount THEN 'cash_amount_mismatch'
             ELSE 'internal_links_match' END AS evidence_result
 FROM missing_allocations m
 JOIN client_company_loan l ON l.company_id=m.company_id AND l.id=m.loan_id
 LEFT JOIN loan_early_settlements s ON s.company_id=m.company_id
   AND s.loan_id=m.loan_id AND s.status='settled' AND s.reversed_at IS NULL
 LEFT JOIN cash_transactions ct ON ct.payment_id=m.payment_id
)
SELECT company_id,loan_id,payment_id,amount,settlement_payment_id,
       settlement_amount,cash_applied_amount,evidence_result
FROM evidence
WHERE NOT (origination_channel='legacy_cashout')
ORDER BY evidence_result,loan_id,payment_id;

WITH missing_allocations AS (
 SELECT pt.company_id,pt.loan_id,pt.id AS payment_id,pt.amount
 FROM payment_transactions pt
 WHERE pt.status='SUCCEEDED' AND pt.purpose='LOAN_REPAYMENT'
 AND pt.direction='INBOUND'
 AND NOT EXISTS (SELECT 1 FROM payment_allocations pa WHERE pa.payment_id=pt.id)
), evidence AS (
 SELECT m.loan_id,m.payment_id,m.amount,
 CASE WHEN s.payment_id IS NULL THEN 'missing_settlement_payment_link'
      WHEN s.payment_id <> m.payment_id THEN 'settlement_payment_mismatch'
      WHEN s.settlement_amount IS DISTINCT FROM m.amount THEN 'settlement_amount_mismatch'
      WHEN ct.payment_id IS NULL THEN 'missing_cash_evidence'
      WHEN ct.direction::text <> 'INBOUND' THEN 'cash_direction_mismatch'
      WHEN ct.applied_amount IS DISTINCT FROM m.amount THEN 'cash_amount_mismatch'
      ELSE 'internal_links_match' END AS evidence_result
 FROM missing_allocations m
 JOIN client_company_loan l ON l.company_id=m.company_id AND l.id=m.loan_id
 LEFT JOIN loan_early_settlements s ON s.company_id=m.company_id
   AND s.loan_id=m.loan_id AND s.status='settled' AND s.reversed_at IS NULL
 LEFT JOIN cash_transactions ct ON ct.payment_id=m.payment_id
 WHERE NOT (l.origination_channel='legacy_cashout')
)
SELECT evidence_result,COUNT(*) AS payment_count,
       COUNT(DISTINCT loan_id) AS loan_count,
       COALESCE(SUM(amount),0)::numeric(18,2) AS amount_maloti
FROM evidence GROUP BY evidence_result ORDER BY evidence_result;
COMMIT;
