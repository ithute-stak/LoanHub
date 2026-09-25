# CDAS TEST UAT checklist

This checklist is for controlled acceptance of the rebuilt manual CDAS integration on `cdas-reintegration`.

Use only the official CDAS TEST environment and authorised TEST records. Do not use production payroll records for smoke testing.

## Preconditions

- branch: `cdas-reintegration`
- latest branch CI is green
- local LoanHub database is isolated from production
- CDAS environment is `test`
- official TEST base URL is configured
- authorised TEST username/password are stored through LoanHub Company Settings
- no LoanHub maintenance/background CDAS worker is running
- request allowance is below the daily limit

## Stage A — read-only acceptance

Complete all read-only checks before any provider mutation.

### A1. Authentication

- [ ] Save TEST configuration
- [ ] Test connection succeeds
- [ ] Authorization token is obtained internally
- [ ] No employee/deduction request is triggered by the connection test
- [ ] Local request-budget counter increases for the outbound login request

Evidence/result:

```text
Date/time:
Tester:
Company:
Result:
Notes:
```

### A2. Employee verification

Endpoint: `/api/employee/getDetails`

- [ ] Enter a known authorised TEST employee number
- [ ] Press **Verify Employee** manually
- [ ] Employee number matches the requested record
- [ ] Name is displayed correctly
- [ ] Surname is displayed correctly
- [ ] DOB is displayed correctly
- [ ] Department is displayed correctly
- [ ] Joining date is displayed correctly
- [ ] Termination date is displayed correctly or is empty when appropriate
- [ ] No background follow-up request occurs

Evidence/result:

```text
Employee number:
Result:
Notes:
```

### A3. Affordability

Endpoint: `/api/employee/check-affordability`

- [ ] Press **Check Affordability** manually
- [ ] Provider response is displayed as an amount
- [ ] No deduction mutation is triggered
- [ ] Request-budget counter increases correctly

Evidence/result:

```text
Employee number:
Affordability returned:
Result:
Notes:
```

### A4. All third-party deductions

Endpoint: `/api/policy/view-all-deduction`

- [ ] Press **View All Deductions** manually
- [ ] Returned records belong to the requested employee
- [ ] Empty-provider response is handled correctly when no records exist
- [ ] No state-changing request is made

Evidence/result:

```text
Employee number:
Record count:
Result:
Notes:
```

### A5. Own deductions by status

Endpoint: `/api/policy/view-deduction`

- [ ] Select a documented deduction status
- [ ] Press **View Own Deductions** manually
- [ ] Returned records belong to the authenticated third party
- [ ] Status filtering behaves as expected
- [ ] Empty-provider response is handled correctly

Evidence/result:

```text
Employee number:
Status code:
Record count:
Result:
Notes:
```

### A6. Active/approved deduction

Endpoint: `/api/policy/get-active-and-approved-deduction`

- [ ] Press **View Active / Approved** manually
- [ ] Returned record matches the TEST employee
- [ ] Missing-record response is handled safely
- [ ] No mutation occurs

Evidence/result:

```text
Employee number:
Deduction ID:
Result:
Notes:
```

### A7. Output file / statement retrieval

Endpoint: `/api/policy/get_document`

- [ ] Select a known TEST year/month
- [ ] Retrieve document type 1 when a TEST output file is available
- [ ] Retrieve document type 2 when a TEST statement is available
- [ ] Filename/response metadata is handled correctly
- [ ] Missing document is reported without retry loops

Evidence/result:

```text
Year/month:
Document type:
Result:
Notes:
```

## Stage B — controlled TEST mutations

Do not begin Stage B until Stage A passes.

Use one deliberately approved TEST deduction record. Record its employee number, item code, reference number and deduction ID before changing state.

### B1. Registration

Endpoint: `/api/policy/add-update-deduction`

- [ ] Explicit confirmation is required in LoanHub
- [ ] Request type is Registration
- [ ] Provider receives one mutation request only
- [ ] Result is audit-logged in LoanHub
- [ ] On session/authentication failure, LoanHub does not automatically replay the write

### B2. Review

- [ ] Explicit confirmation required
- [ ] Correct existing TEST deduction is targeted
- [ ] Provider receives one mutation request only
- [ ] Result is audit-logged

### B3. Approval

- [ ] Explicit confirmation required
- [ ] Correct TEST deduction is targeted
- [ ] Provider receives one mutation request only
- [ ] Result is audit-logged

### B4. Change / update

- [ ] Explicit confirmation required
- [ ] Changed values are deliberate and recorded before submission
- [ ] Provider receives one mutation request only
- [ ] Updated provider record is re-read separately after the write

### B5. Modify active deduction

Endpoint: `/api/policy/modify-active-deduction`

- [ ] Explicit confirmation required
- [ ] Only a deliberately selected active/approved TEST deduction is used
- [ ] Provider receives one mutation request only
- [ ] Provider validation errors are surfaced without automatic replay
- [ ] Result is audit-logged

### B6. Settlement

Endpoint: `/api/policy/settled-deduction`

- [ ] Explicit confirmation required
- [ ] Settlement reason is deliberately selected
- [ ] Provider receives one mutation request only
- [ ] Result is audit-logged
- [ ] Deduction is re-read separately after settlement to confirm final state

## Stage C — safety acceptance

- [ ] Opening `/company/cdas` generates no provider request
- [ ] Merely typing an employee number generates no provider request
- [ ] Request allowance check contacts only LoanHub, not CDAS
- [ ] Login and re-login consume local request-budget slots
- [ ] Read calls may reauthenticate safely after an inactive session
- [ ] State-changing calls never automatically replay after an inactive/expired session
- [ ] Local quota protection blocks the 401st outbound request for the configured API account/day
- [ ] TEST credentials are not present in Git history
- [ ] No background crawler, roster sync, scheduler or automatic lifecycle process is running

## Final UAT decision

```text
Read-only Stage A: PASS / FAIL
Mutation Stage B: PASS / FAIL / NOT EXECUTED
Safety Stage C: PASS / FAIL

Open defects:

Production approval: NOT APPROVED / APPROVED SEPARATELY
Tester:
Date:
```

Passing this checklist does not itself authorize a production merge or deployment. Production approval remains a separate explicit decision.
