# LoanHub Experian Credit Bureau Integration

## Purpose

LoanHub uses one centrally secured Experian provider connection controlled by the **Platform Owner**. Lending companies never store or view Experian OAuth credentials. Each company separately chooses whether to use Experian and keeps its own credit-risk policy, borrower consent evidence and company/application-scoped enquiry history.

A borrower identity remains global in LoanHub, but each Experian enquiry belongs to the lending company and exact loan application that lawfully requested the report.

The integration deliberately separates **Experian OAuth authentication** from the **product-specific bureau API contract**. OAuth is common across Experian Developer Platform products. The request endpoint, request JSON and response fields vary by the product enabled in the Experian app and must be copied from that product's API documentation rather than guessed by LoanHub.

## 1. Experian Developer Portal

1. Sign in to the Experian Developer Portal.
2. Open **My Apps**.
3. Create or open the application that will be used by LoanHub.
4. Add the approved product, for example **Experian One for Customer Acquisition API** where it is available for your market and contract.
5. Record the application's **Client ID** and **Client Secret**.
6. Keep the Developer Portal username and password available for the OAuth token request.
7. Open the selected product's API documentation and record:
   - the bureau request endpoint path;
   - the request JSON schema and required fields;
   - the response JSON fields for the data LoanHub will normalize;
   - sandbox test identities supplied by Experian.

Do not put Client Secrets, passwords or access tokens in source code, `.env.example`, screenshots, tickets or Git commits.

## 2. Platform Owner configuration

Sign in as the LoanHub Platform Owner/System Owner and open:

**Platform configuration → Experian credit bureau**

or directly:

`/superadmin/control/integrations/experian`

The Platform Owner configures the only provider credential bundle used by LoanHub.

| LoanHub setting | Experian EMEA host |
| --- | --- |
| Sandbox | `https://sandbox-eu-api.experian.com` |
| UAT | `https://uat-eu-api.experian.com` |
| Production | `https://eu-api.experian.com` |

Enter all four values together when adding or rotating credentials:

- Developer Portal username
- Developer Portal password
- Client ID
- Client Secret

LoanHub encrypts the bundle in platform-owned storage. The browser cannot retrieve the secret values after saving.

Older company-level Experian credential copies are retired by the Platform Owner migration. They are not reused after the central connection is introduced.

## 3. Test OAuth first

Keep the central Experian connection disabled while setting it up. Save the credentials and click **Test OAuth connection**.

A successful test confirms that LoanHub can obtain a bearer access token from:

`/oauth2/v1/token`

LoanHub caches access tokens only in backend memory and refreshes before expiry. Access and refresh tokens are never stored in the LoanHub database.

If authentication fails, verify the selected environment, Developer Portal password, Client ID and Client Secret. A Developer Portal password change requires rotating the central platform credential bundle.

## 4. Configure the product-specific bureau request

This configuration also belongs to the Platform Owner because it describes the Experian product contract shared by all participating LoanHub companies.

### Endpoint path

Enter only the relative path shown by Experian, for example the value beginning with `/...` from the product API reference. LoanHub rejects absolute URLs so the configuration cannot become an arbitrary server-side HTTP proxy.

### Request template

Copy the product's documented JSON request body and replace borrower/application values with LoanHub placeholders.

Available placeholders include:

- `{{full_name}}`
- `{{national_id}}`
- `{{passport_number}}`
- `{{date_of_birth}}`
- `{{phone}}`
- `{{email}}`
- `{{borrower_id}}`
- `{{application_id}}`
- `{{application_reference}}`
- `{{requested_amount}}`
- `{{term_count}}`
- `{{purpose}}`
- `{{permissible_purpose}}`
- `{{consent_reference}}`

Example templating shape:

```json
{
  "identity": {
    "nationalId": "{{national_id}}",
    "dateOfBirth": "{{date_of_birth}}"
  },
  "application": {
    "reference": "{{application_reference}}",
    "amount": "{{requested_amount}}"
  }
}
```

The example demonstrates LoanHub templating only. Replace all field names with the exact names documented for the Experian product enabled on the app.

### Response mapping

Map LoanHub's normalized fields to dotted JSON paths in the documented Experian response.

Supported normalized names include:

- `provider_reference`
- `score`
- `risk_band`
- `identity_match`
- `open_accounts_count`
- `defaults_count`
- `judgments_count`
- `collections_count`
- `recent_enquiries_count`
- `monthly_commitments`
- `total_balance`

Example mapping shape:

```json
{
  "score": "documented.path.to.score",
  "risk_band": "documented.path.to.riskBand",
  "monthly_commitments": "documented.path.to.monthlyCommitments"
}
```

The paths above are illustrative. Use the exact response contract supplied by Experian.

## 5. Platform readiness gate

LoanHub marks the central provider **Ready for company use** only after all of the following are true:

1. encrypted credentials exist;
2. the latest OAuth test succeeded;
3. the relative bureau endpoint is configured;
4. the request template is configured;
5. the response mapping is configured;
6. the Platform Owner has enabled Experian.

Companies can see this readiness state but cannot see the credentials or provider mapping.

## 6. Lending company configuration

Company Owner/Admin opens:

**Credit Origination → Experian credit bureau**

The company page no longer asks for Experian username/password, Client ID, Client Secret, endpoint or provider JSON mapping. It shows the central platform readiness status as read-only.

The company may configure only its lending policy:

- enable/disable Experian for the company;
- maximum report age;
- whether a report is required before affordability;
- whether bureau commitments should be considered in affordability;
- debt treatment mode (`max`, `bureau_only`, `declared_plus_bureau`);
- optional decline/refer score thresholds;
- whether defaults are blocking;
- whether identity match is required.

The company cannot enable the operational workflow from the UI until the Platform Owner connection is ready.

## 7. Run a credit check

Open the company Experian workspace and select a LoanHub origination application.

Before LoanHub sends the request, staff must record:

- confirmed borrower consent;
- consent method;
- optional consent/evidence reference;
- permissible purpose (`credit_application`).

LoanHub resolves the borrower identity and application facts server-side. It then sends the request through the **central Platform Owner Experian connection**, while the resulting enquiry remains owned by the requesting lending company.

## 8. Data storage and tenancy

Each canonical `credit_bureau_enquiries` row stores the company, branch, borrower, application, requesting user, consent evidence, request/completion time and normalized result.

The complete provider response is stored only as encrypted provider payload data. Standard company APIs do not expose it.

A report requested by Company A is not returned as Company B's report merely because both companies can identify the same global borrower.

Provider secrets are platform-owned; enquiry/report data remains company/application-scoped.

## 9. Debt comparison

LoanHub shows borrower-declared monthly debt beside the latest company/application-specific Experian monthly commitments and calculates the difference. It does **not** silently overwrite the borrower's declared obligations.

The company policy controls how bureau information should be treated. Automatic credit-decision enforcement should only be enabled after the exact subscribed Experian response fields and score semantics have been confirmed for the relevant market/product.

## 10. Moving to UAT and production

Environment changes are Platform Owner operations. Do not reuse sandbox assumptions in production.

For each environment:

1. Platform Owner rotates the credential bundle;
2. selects Sandbox/UAT/Production;
3. verifies the product endpoint and JSON contract;
4. tests OAuth;
5. runs approved product test cases;
6. confirms response mapping;
7. confirms company consent/permissible-purpose controls;
8. enables the central provider only after validation.

Companies do not receive separate production secrets unless LoanHub's future commercial model explicitly changes to per-tenant Experian contracts.

## 11. First deployment after this change

Run the new database migration before opening the Platform Owner Experian screen:

```bash
cd apps/backend
alembic upgrade head
```

The migration creates `platform_credit_bureau_configurations` and retires any legacy company-level Experian credential copies.

## 12. Troubleshooting

### `The Platform Owner has not configured Experian yet`
Sign in as Platform Owner and complete **Platform configuration → Experian credit bureau**.

### Platform connection shows `Not ready`
Check the readiness cards for credentials, OAuth, endpoint, request template, response mapping and platform enablement.

### Authentication rejected
Check the platform environment, Developer Portal username/password and Client ID/Secret. Confirm the Experian app has access to the selected product.

### Company cannot enable Experian
The platform readiness gate has not passed. Company staff cannot bypass the central provider controls.

### Product endpoint/template not configured
OAuth may be ready, but the Platform Owner still needs the exact endpoint and JSON contract from the selected product's API documentation.

### HTTP 401/403 on bureau enquiry
OAuth may work while the app lacks permission for the bureau product/endpoint. Confirm product access in Experian My Apps or with the Experian account/API support team.

### Score or commitments show `not mapped`
The bureau call succeeded but the Platform Owner response mapping does not point to the correct fields. Compare the encrypted provider response through a controlled support/audit process with the product API documentation, then correct the mapping. Never expose raw bureau responses to ordinary company users.
