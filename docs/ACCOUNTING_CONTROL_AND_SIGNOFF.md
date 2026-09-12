# Accounting control and professional sign-off

LoanHub enforces double-entry journal construction in the application and now runs `scripts/accounting_integrity_check.py` as a release gate after a real PostgreSQL migration. The checker rejects journal headers whose debit/credit totals differ, journal-line aggregates that do not balance, lines that contain both a debit and a credit, and zero-value lines. This is an automated software control; it is not a professional accounting opinion.

## Production control cycle

Daily operations should reconcile cash/bank balances, disbursements, repayments, fees, interest, suspense items and loan sub-ledger balances to the general ledger. Exceptions must have an owner, evidence and resolution date. Period close should lock or formally control back-dated posting, run the integrity checker, reconcile provider/bank statements and generate an immutable close evidence pack.

Before a serious SME lender relies on LoanHub for statutory or management accounts, a qualified accountant/controller must review the chart of accounts, recognition policy, interest/fee treatment, arrears/default/write-off handling, tax treatment, rounding, period close, reversals, suspense handling and the mapping from every lending event to journal entries. Where IFRS or local regulatory reporting applies, that review must explicitly confirm the applicable treatment.

## Sign-off record

Professional accounting sign-off status: **PENDING EXTERNAL REVIEW**.

The production launch file should record: reviewer name and professional designation; organization; scope/version/commit SHA; sample transactions reviewed; opening-balance and migration validation; exceptions raised; remediation references; final approval/rejection; signature; and date. Re-sign after material accounting-rule changes.

Software release CI proves the ledger is mathematically balanced and regression-tested. It must never be presented as proof that account classification, tax treatment or statutory reporting policy has been certified by a professional accountant.
