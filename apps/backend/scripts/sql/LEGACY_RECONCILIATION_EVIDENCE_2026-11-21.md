# Legacy repayment reconciliation — production evidence (2026-11-21)

## Scope and guardrails
Read-only investigation of migration-related differences between repayment installment paid amounts and linked payment allocations. This report records observed internal accounting consistency, **not independent confirmation of historical cash receipt**. No loan balances, payment allocations, settlements, or LoanHub Calculator behavior should be altered based on these findings alone.

## Production classification (2026-11-19)
- 226 discrepant installments across 105 legacy loans; aggregate installment paid-versus-allocation gap M325,223.29.
- 216 installments across 97 loans, M316,323.57: `legacy_opening_balance_candidate`; independent historical source verification outstanding.
- 10 installments across 8 loans, M8,899.72: `legacy_mixed_live_evidence_review`.

## Eight mixed-evidence loans
Read-only `legacy_opening_balance_crosscheck.sql` compared loan amount paid minus successful live repayments to active installment paid-minus-allocated values. Six loans matched exactly. Two did not when superseded installments were excluded:

| Loan | Inferred historical opening | Active installment gap | Superseded WAIVED paid amount | Remaining numerical difference |
| --- | ---: | ---: | ---: | ---: |
| LEG-5111-DA3441 | M643.00 | M642.92 | M0.08 | M0.00 |
| LEG-B5101-8D1939 | M418.00 | M417.60 | M0.40 | M0.00 |

The corrected read-only `legacy_opening_rounding_drilldown.sql` ran successfully on production 2026-11-21 and returned six installment rows for these two loans. The M0.08 and M0.40 appear in installment 2, both `WAIVED` and `is_superseded=true`. Installment 3 is also waived and superseded, with paid amount M0.00. Installment 1 is active and `PAID`, with paid amounts M642.92 and M417.60 respectively. Both loans' migration calculation breakdowns show `historical_payment_allocation=opening_balance_only_no_loanhub_cash_transaction` and completed early settlement metadata.

Across all eight mixed-evidence loans: inferred historical opening balance M8,900.20 = active installment allocation gap M8,899.72 + superseded WAIVED paid amounts M0.48. This is an **internal numerical explanation**, not proof that historical funds were received. The causal business reason for retaining those small paid amounts on superseded installments remains to be established from migration/settlement implementation and source records. Do not label the M0.48 as mere rounding without evidence.

## Remaining work / release gates
1. Validate legacy source book/receipts against historical opening balances for all 105 affected loans, especially the 97 historical-only candidates.
2. Review migration and early-settlement implementation for the two superseded WAIVED paid amounts; preserve current production records until policy and evidence are confirmed.
3. Recheck GitHub CI on the latest PR commit; review the read-only scripts before merging.
4. Do not activate Principal x% live posting until its separate readiness controls and financial verification are approved. LoanHub Calculator remains unchanged.

## Reproduction
- `apps/backend/scripts/sql/active_installment_allocation_deltas.sql`
- `apps/backend/scripts/sql/legacy_mixed_evidence_eight_loans.sql`
- `apps/backend/scripts/sql/legacy_opening_balance_crosscheck.sql`
- `apps/backend/scripts/sql/legacy_opening_rounding_drilldown.sql`

All production scripts should be run with read-only transaction semantics and reviewed outputs; no corrective SQL writes are authorized.
