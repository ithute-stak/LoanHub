# LoanHub v1.0 Project Overview

LoanHub is a multi-tenant loan marketplace and loan-management platform for Lesotho. Independent loan companies operate within isolated tenant and branch scopes, borrowers broadcast funding requests and compare offers, and the platform owner governs companies, commercial plans, risk, incidents and service-wide reporting.

## Functional modules

### Identity and access
Login, refresh/logout, account status, tenant context, branch scope and platform role switching.

### Company administration
Company registration, approval, settings, branches, staff memberships and role assignment.

### Borrower management
Borrower registration, personal profile, employment, affordability and consent.

### Marketplace
Broadcast requests, redacted discovery, paid/subscription unlocks and lender offers.

### Loan servicing
Accepted loans, disbursement, repayment schedules, allocations, overdue and completion states.

### Billing and payments
Plans, subscriptions, unlock fees, platform fees and provider-neutral payment records.

### Notifications and audit
Persistent actionable notifications, CRUD transparency and request correlation.

### System-error monitoring
Grouped fingerprints, rate-limited owner alerts and safe ordinary-user responses.

### Chat and presence
Direct/group conversations, one shared socket, online status, typing, read state and voice notes.

### Managed files
Permissioned upload/download, checksums, encryption, visibility and report storage.

### Employees and performance
Employee profiles, departments, managers, goals, reviews and analytics.

### Accounting
Chart of accounts, balanced journals, posting, trial balance, profit/loss and balance sheet.

### Reports and reconciliation
Manual and scheduled PDF/CSV reports plus midnight business reconciliation.

### Deployment and operations
One Docker Compose stack, Caddy TLS, PostgreSQL, Redis, CI/CD and backups.

## Release metrics

- 146 backend route operations, including one WebSocket endpoint.
- 37 mapped database models.
- 51 Next.js pages.
- 34 ordered Alembic revisions with one head: `f1a9c4e7b620`.
- 149 backend Python files and 267 frontend TypeScript/TSX files in the documented snapshot.
