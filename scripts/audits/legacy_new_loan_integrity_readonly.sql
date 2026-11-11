-- LoanHub incident audit: read-only evidence for legacy/new-loan overlap.
-- PostgreSQL. Run with a SELECT-only production role; never run using a migration role.
-- No customer identity fields are selected. Review each loan reference inside the approved
-- operator environment; never export this result to a public CI artifact.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '30s';

-- Separate explicit legacy capture linkage from borrower identity. A borrower is
-- allowed to have BOTH completed historic loans and active current loans.
WITH legacy_linked AS (
  SELECT DISTINCT loan_id FROM legacy_loan_captures WHERE loan_id IS NOT NULL
), paired_borrowers AS (
  SELECT DISTINCT l.company_id, l.borrower_id
  FROM client_company_loan l
  JOIN legacy_linked linked ON linked.loan_id = l.id
  WHERE EXISTS (
    SELECT 1 FROM client_company_loan newer
    WHERE newer.company_id = l.company_id AND newer.borrower_id = l.borrower_id
      AND NOT EXISTS (SELECT 1 FROM legacy_linked ll WHERE ll.loan_id = newer.id)
  )
)
SELECT
  'borrowers_with_legacy_and_nonlegacy_loans' AS metric, count(*) AS count
FROM paired_borrowers
UNION ALL
SELECT 'active_nonlegacy_loans_in_overlap', count(*)
FROM client_company_loan newer
JOIN paired_borrowers pair ON pair.company_id = newer.company_id
  AND pair.borrower_id = newer.borrower_id
WHERE newer.status::text = 'active'
  AND NOT EXISTS (SELECT 1 FROM legacy_linked ll WHERE ll.loan_id = newer.id)
UNION ALL
SELECT 'completed_legacy_loans_in_overlap', count(*)
FROM client_company_loan legacy
JOIN paired_borrowers pair ON pair.company_id = legacy.company_id
  AND pair.borrower_id = legacy.borrower_id
WHERE legacy.status::text = 'completed'
  AND EXISTS (SELECT 1 FROM legacy_linked ll WHERE ll.loan_id = legacy.id);

-- A payment allocation must belong to the SAME loan, borrower and company as
-- the attached installment. Nullable payment.loan_id is surfaced separately.
SELECT
  COUNT(*) FILTER (WHERE p.loan_id IS NOT NULL AND p.loan_id <> ri.loan_id)
    AS cross_loan_allocations,
  COUNT(*) FILTER (WHERE p.company_id IS NOT NULL AND p.company_id <> l.company_id)
    AS cross_company_allocations,
  COUNT(*) FILTER (WHERE p.borrower_id IS NOT NULL AND p.borrower_id <> l.borrower_id)
    AS cross_borrower_allocations,
  COUNT(*) FILTER (WHERE p.loan_id IS NULL)
    AS payment_allocations_missing_loan_id
FROM payment_allocations pa
JOIN payment_transactions p ON p.id = pa.payment_id
JOIN repayment_installments ri ON ri.id = pa.installment_id
JOIN client_company_loan l ON l.id = ri.loan_id;

-- Completion without ordinary payments can be legitimate when settled by top-up.
-- Preserve this distinction rather than blindly reopening completed loans.
SELECT
  l.loan_reference,
  l.status::text AS loan_status,
  l.total_repayable,
  l.amount_paid,
  l.balance,
  EXISTS (SELECT 1 FROM legacy_loan_captures c WHERE c.loan_id = l.id)
    AS linked_to_legacy_capture,
  EXISTS (SELECT 1 FROM loan_top_up_settlements s
          WHERE s.parent_loan_id = l.id AND s.status = 'settled')
    AS linked_to_topup_settlement,
  EXISTS (SELECT 1 FROM payment_transactions p
          WHERE p.loan_id = l.id AND p.direction::text = 'INBOUND'
            AND p.status::text = 'SUCCEEDED')
    AS has_successful_inbound_payment
FROM client_company_loan l
WHERE l.status::text = 'completed'
  AND l.total_repayable > l.amount_paid + 0.01
ORDER BY l.loan_reference;

ROLLBACK; -- Explicit rollback documents zero persistence.
