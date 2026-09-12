# LoanHub - Marketable Ithute Solutions Edition

LoanHub is a multi-tenant loan-management and loan-marketplace platform developed and maintained by Ithute Solutions. It gives each lending company an isolated operating workspace while preserving platform-wide governance for the LoanHub owner.

## Product areas

- Multi-company and multi-branch tenant management
- Role-based company operations
- Borrower loan-request marketplace and competing lender offers
- Loan origination, disbursement, schedules, repayments and collections
- Subscription plans, pay-per-request unlocking and transaction billing
- Persistent notifications, realtime WebSocket delivery and complete audit history
- Employee records, performance goals and performance reviews
- WhatsApp-style internal chat with file and PDF sharing
- Secure file centre with tenant and branch visibility rules
- Double-entry accounting foundation
- Daily, weekly, monthly and annual operational reports
- Branch, company and platform analytics
- System-error monitoring and resolution workflows
- Ithute Solutions branding across the user interface and generated reports

## Human-friendly references

User-facing screens no longer expose raw UUID values as primary labels. The interface shows business references such as:

- `PAY-2026-8A74B113` for a payment
- `BRN-2026-14CC90F2` for a branch
- `RPT-20260715-7C42A1D9` for a report
- meaningful company, borrower, employee and actor names where available

Database UUIDs remain internal identifiers and may still appear in developer logs, API payloads or support diagnostics.

## New marketability modules

### Platform chat

The chat module supports direct and group conversations, unread badges, typing indicators, realtime message delivery, polling fallback, message read states, document attachments, image attachments and secure downloads.

This is a WhatsApp-style business-chat foundation. It is not the WhatsApp service, does not connect to Meta WhatsApp APIs, and does not currently implement end-to-end encryption.

### File centre

Files use one managed storage layer shared by chat, generated reports and document-centre uploads. Visibility can be private, conversation, branch, company, confidential or platform-wide. Access is checked against database tenant and participant relationships.

The supplied deployment stores files in a persistent local/Docker volume. For high-availability production use, implement the same service interface with S3, MinIO or another object-storage provider.

### Accounting

The accounting module provides a chart of accounts, balanced journal entries, posting, trial balance, profit-and-loss statement and balance sheet. Successful payment transactions can automatically create accounting entries.

The accounting engine is a strong double-entry foundation, but account mappings, tax treatment and statutory reporting should be reviewed by a qualified accountant before production use.

### Automated reports

Authorised users can generate or schedule PDF/CSV reports at branch, company or platform scope. Frequencies include daily, weekly, monthly and annual. Reports include operations, lending, payments, performance and accounting measurements.

Scheduled recipient addresses are stored for future delivery integration. Automatic email delivery is not yet implemented; generated reports are available in the report centre and file centre.

## Main portals

### Platform owner

- `/superadmin`
- `/superadmin/companies`
- `/superadmin/plans`
- `/superadmin/payments`
- `/superadmin/accounting`
- `/superadmin/reports`
- `/superadmin/chat`
- `/superadmin/files`
- `/superadmin/performance`
- `/superadmin/activity`
- `/superadmin/system-errors`

### Company tenant

- `/company`
- `/company/marketplace`
- `/company/products`
- `/company/loans`
- `/company/payments`
- `/company/accounting`
- `/company/reports`
- `/company/chat`
- `/company/files`
- `/company/employees`
- `/company/performance`
- `/company/activity`
- `/company/settings`

### Borrower

- `/borrower`
- `/borrower/requests`
- `/borrower/loans`
- `/borrower/payments`
- `/borrower/chat`
- `/borrower/files`
- `/borrower/notifications`

## Database migration

Latest Alembic head:

```text
f1a9c4e7b620
```

Always create a backup and test the migration on staging before production.

## Important provider status

The database and workflow layers support M-Pesa and EcoCash concepts, but live provider API calls, official authentication, callback-signature validation, settlement reconciliation and certification are not included. Those require merchant onboarding and current official provider documentation.
