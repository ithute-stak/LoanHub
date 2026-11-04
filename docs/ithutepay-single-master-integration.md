# LoanHub → IthutePay, initial single-company master-merchant integration

Requested mode: the sole LoanHub lender uses IthutePay's **master merchant** rather than its own M-PESA shortcode; IthutePay adds **zero platform fees** (in/out: LSL 0.00 and 0%). Direct service-to-service integration, no Golink requirement.

## Stage 1 (this change): identity discovery only

Run in the current LoanHub backend container, with its existing production DB connection:

```sh
python /app/scripts/ithutepay_master_company_preflight.py
```

The script uses LoanHub's `loan_companies` table (source of truth), requires **exactly one** company, prints its ID and name, and makes **no writes**. If 0 or multiple companies exist, it refuses implicit selection. Confirm the displayed legal entity is the intended owner/beneficiary before linking.

## Stage 2: binding, provider authorization, and zero fee policy (not activated)

- Verify the exact LoanHub company ID against the authorized IthutePay platform master merchant identity. Do not assume the two companies are identical based only on being the sole LoanHub company.
- Check IthutePay's current `PlatformMerchantSettings`, master merchant, company owner authorization, permitted M-PESA shortcode use, and regulatory/provider agreement for shared custody. IthutePay currently blocks approving `master_shortcode` tenants.
- Decide whether the company is *the master merchant legal entity* or a distinct tenant using that master. Do not silently create a self-tenant contract where IthutePay expressly disallows it.
- Set explicitly agreed IthutePay platform charges **0.00 fixed and 0% percentage** for both incoming/outgoing payments. Vodacom/provider fees, taxes and statutory costs are **not** assumed to be zero.
- Use a scoped, authenticated and signed LoanHub→IthutePay integration. Never reuse global keys across other tenant companies; bind the exact company and platform merchant IDs server-side.
- Add idempotency, callback verification, loan/company matching, reconciliation, audit trails, and a guarded disabled-by-default activation switch before sending financial instructions.
- Preserve LoanHub's existing optional own-shortcode path and IthutePay's existing direct M-PESA adapter. Golink remains optional.
- Do not enable provider payments, payout routes, background settlement processing or shared custody until those checks are complete.

No public customer-facing action, production merchant change, pricing modification, payout or migration is included in Stage 1.
