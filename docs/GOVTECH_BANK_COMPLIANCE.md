# GovTech and regulated-institution readiness

LoanHub now treats a bank or another lending body as an isolated institution tenant. This release adds operational controls and evidence capture; it does **not** certify legal compliance, grant a banking licence, or imply endorsement by the Government of Lesotho, the Central Bank of Lesotho, GovStack, UNDP, or the Digital Public Goods Alliance.

## Institution tenants

Supported classifications:

- Loan company
- Commercial bank
- Microfinance institution
- Financial cooperative
- Development finance institution
- Government lending programme

A prospective institution can create a pending profile at `/register-institution`. The system owner must verify and approve the tenant before it becomes active. Platform approval is separate from regulatory authorisation.

## Bank and institution roles

| Role | Scope | Primary responsibility |
| --- | --- | --- |
| Institution owner / board representative | Institution | Accountability and tenant ownership |
| Institution administrator | Institution | Configuration, staff and delegated administration |
| Branch manager | Branch | Branch people, portfolio and operations |
| Operations officer | Branch | Service delivery, controls and workflows |
| Loan officer | Branch | Origination and loan administration |
| Credit analyst | Branch | Affordability and credit recommendations |
| Risk manager | Institution | Credit, operational and enterprise risk |
| Finance officer | Institution or branch | Accounting, payments and financial controls |
| Treasury officer | Institution | Liquidity, cash, funding and reconciliation |
| Collections officer | Branch | Arrears and recoveries |
| Compliance officer | Institution | Regulatory compliance monitoring |
| AML/CFT officer | Institution | Due diligence, screening and AML/CFT controls |
| Regulatory reporting officer | Institution | Regulatory returns and submissions |
| Data-protection officer | Institution | Privacy, consent, retention and rights |
| Internal auditor | Institution | Independent assurance |
| Information-security officer | Institution | Cybersecurity, incidents and resilience |
| Customer service / complaints officer | Branch | Customer support and complaints |
| HR manager | Institution | Workforce governance |
| Performance manager | Institution | Targets and performance |
| IT support | Institution | Availability, integrations and support |

Roles use least-privilege permission groups. Institution-wide control roles do not silently receive loan-write, cash, or branch-management rights.

## Governance workspace

Company settings includes a **Governance & compliance** tab with:

- regulator and licence records, expiry monitoring, bank code, and SWIFT/BIC;
- named AML/CFT, privacy, reporting, and complaints contacts;
- privacy notice, retention, consent, and controlled data-export controls;
- responsible-AI declarations for human review, explanations, and bias monitoring;
- accessibility, English/Sesotho, and low-bandwidth readiness;
- business-continuity and incident-response exercise records;
- GovStack and DPG assessment status;
- a computed readiness score and missing-role list.

Every governance-profile update is tenant-scoped and written to the audit trail. System owners can inspect a selected institution using an explicit company identifier.

## GovStack building-block mapping

| Capability | Status | LoanHub implementation |
| --- | --- | --- |
| Registry | Implemented | Tenant, branch, staff, borrower, product, and loan registries |
| Identity | Integration-ready | KYC and consent records; an authorised national-ID endpoint is still required |
| Workflow | Implemented | Versioned templates and auditable workflow instances |
| Payment | Implemented | Payment ledger, proof references, and provider-ready channels |
| Information mediator | Integration-ready | Scoped tenant APIs, API keys, and signed webhooks |
| Notification | Implemented | In-app and real-time notifications |
| Reporting | Implemented | Generated reports and dual-control regulatory submissions |
| Audit | Implemented | Actor, tenant, record, changed-field, and event history |
| Responsible AI | Implemented as governance controls | Human-review, explanation, and fairness-control evidence |

“Integration-ready” means the internal boundary exists; it does not mean an external service is connected.

## Dependencies before production claims

The following remain external or organisational work:

1. Obtain official integration agreements, endpoint specifications, credentials, test environments, and data-sharing authority.
2. Have Lesotho legal and regulatory specialists approve the licence, AML/CFT, privacy, consumer-protection, reporting, records-retention, and cybersecurity interpretations.
3. Configure named control owners and segregate duties for each institution.
4. Complete threat modelling, penetration testing, accessibility testing, disaster-recovery exercises, and incident simulations.
5. Validate regulatory report formats and submission channels with the competent authority.
6. Publish the supported API contract and decide whether licensing and repository openness meet the DPG Standard.
7. Run real model governance and outcome monitoring before enabling AI-supported credit decisions.

## Authoritative references

- Central Bank of Lesotho, Financial Surveillance and Integrity Division: https://centralbank.org.ls/financial-surveillance-and-integrity-division/
- Central Bank of Lesotho, Banking Supervision and Financial Stability: https://centralbank.org.ls/banking-supervision-and-financial-stability/
- Central Bank of Lesotho, Legislations: https://centralbank.org.ls/legislations/
- GovStack Building Block Approach: https://specs.govstack.global/architecture/4-interoperability-architecture/4.5-building-block-approach
- GovStack 2.0 specifications announcement: https://govstack.global/news/govstack-2-0-0-core-specifications-are-live-heres-the-rollout-and-alignment-plan/
- Digital Public Goods Standard: https://www.digitalpublicgoods.net/standard
