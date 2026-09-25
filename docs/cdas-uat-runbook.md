# CDAS TEST UAT runbook

This runbook is for controlled acceptance of the rebuilt LoanHub CDAS integration against the authorised CDAS TEST environment.

It must not be used to exercise deduction mutations against production payroll records.

## Preconditions

- branch: `cdas-reintegration`
- local LoanHub database, not the production database
- local frontend points to the local backend
- CDAS environment is set to `test`
- authorised CDAS TEST username/password are entered through LoanHub Company Settings
- no maintenance/background worker is required for this UAT
- use a known authorised CDAS TEST employee number for provider reads
- use a deliberately approved TEST deduction record before exercising write operations

## Local branch check

```bash
cd ~/Documents/GitHub/production_repo/LoanHub
git fetch origin
git switch cdas-reintegration
git pull --ff-only origin cdas-reintegration
git log -1 --oneline
git status
```

Do not continue if the working tree contains unexpected source changes.

## Safe local stack

The repository root `compose.yaml` has production-oriented defaults, so CDAS UAT must override them and should start only:

- PostgreSQL
- Redis
- migration job
- backend
- frontend

Do not start the `maintenance` service for this acceptance run.

Recommended local URLs:

- LoanHub frontend: `http://localhost:13000`
- LoanHub API: `http://localhost:18000/api/v1`
- backend readiness: `http://localhost:18000/health/ready`

Use a dedicated Compose project name such as `loanhub-cdas-uat` so its database and Redis volumes are isolated from other LoanHub stacks.

## CDAS configuration

Inside LoanHub:

`Company -> Settings -> CDAS Authentication`

Configure:

- Environment: `TEST`
- Base URL: official CDAS TEST base URL supplied for the integration
- Username: authorised TEST API username
- Password: authorised TEST API password
- Timeout: 20 seconds unless provider conditions require otherwise
- Authentication enabled: yes

Do not put the CDAS password into Git, source files or committed environment files.

## Gate A: authentication

Press `Test Connection`.

Expected result:

1. LoanHub sends the documented login request.
2. CDAS returns an authorization token.
3. LoanHub reports the configuration as connected.
4. No employee, affordability or deduction request is triggered automatically.

Stop and diagnose here if authentication fails.

## Gate B: request allowance

Open:

`Company -> CDAS`

Press `Check request allowance`.

This reads LoanHub's local request-budget counter only; it must not contact CDAS.

Confirm:

- daily limit is 400
- used count is plausible for the current Lesotho calendar day
- remaining count is non-negative

Login and re-login HTTP calls count against the local allowance because they are outbound provider requests.

## Gate C: employee verification

Enter a known authorised CDAS TEST employee number and press `Verify Employee`.

Confirm the returned fields match CDAS TEST:

- EmployeeNo
- Name
- Surname
- DOB
- Department
- JoiningDate
- TerminationDate

Do not use LoanHub sandbox sample national IDs as if they were CDAS employee numbers.

## Gate D: affordability

For the same TEST employee, press `Check Affordability`.

Confirm:

- LoanHub displays the provider amount accurately
- the value is not being sourced from LoanHub's own borrower income data
- one deliberate provider action corresponds to one requested lookup, except for a necessary read-only session re-login

## Gate E: deduction reads

Run the following one at a time:

1. `View All Deductions`
2. `View Own Deductions` for a known status
3. `View Active / Approved`

Compare LoanHub's result with the CDAS TEST record where possible.

No write operation is required to pass this gate.

## Gate F: documents

For a month/year known to contain TEST data, manually request:

- output file, or
- statement

Confirm filename/content metadata matches the provider response and that merely visiting the documents screen performs no provider call.

## Gate G: controlled deduction lifecycle

Only begin this gate after A-F pass.

Use one deliberately approved TEST deduction record. Do not improvise with live payroll data.

Recommended sequence:

1. Registration
2. Review
3. Approval
4. Change/Update if required by the test case
5. Active/approved modification if applicable
6. Settlement

For each action:

- review the outgoing values before confirming
- use the management-only operations workspace
- confirm explicitly
- verify the provider response before moving to the next state
- re-query the record after the write rather than assuming local success means provider state changed
- check the LoanHub audit trail

## Mutation retry rule

If CDAS reports an expired/inactive session during a state-changing request, LoanHub must not automatically replay that write.

The operator must first reconcile the provider state. Only then may a new explicit action be submitted.

This protects against duplicate or ambiguous deduction mutations.

## Completion criteria

CDAS UAT is complete only when:

- authentication works in TEST
- employee details match the provider
- affordability matches the provider
- deduction read endpoints return expected TEST records
- request-budget accounting behaves correctly
- document retrieval is verified with TEST data
- one approved TEST deduction can progress through the agreed lifecycle without duplicate writes
- modification is verified when applicable
- settlement is verified when applicable
- provider mutations appear in the LoanHub audit trail
- no background CDAS activity is observed
- no production CDAS credentials or production payroll records were used for unsafe testing

## Production gate

Passing this runbook does not itself authorize deployment.

PR #78 must remain unmerged until explicit production approval is given. Production deployment should follow the repository's production release process and deployment safety guard.
