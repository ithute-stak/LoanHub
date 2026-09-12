# LoanHub Native HRMS Foundation

This release introduces Human Resource Management as a first-class, multi-tenant LoanHub module.

## Included

- HR dashboard and company navigation.
- Organisation departments, positions and shifts.
- Attendance event register supporting manual, fingerprint, RFID, face, QR, mobile GPS and offline-sync sources.
- Configurable leave types and approval workflow.
- Payroll periods, employee entries, calculation foundation and controlled status lifecycle.
- Recruitment vacancies and candidate database.
- Training programmes and employee enrolment.
- Company asset register and employee assignments.
- Employee self-service summary endpoint.
- Company and branch scope checks.
- PostgreSQL migration `z9n3p5q7r800`.

## Existing LoanHub modules reused

- Employee profiles and reporting lines.
- Performance goals and formal reviews.
- Company branches and staff memberships.
- Authentication, roles, tenant context and audit columns.
- Managed files, notifications, reports and accounting foundations.

## Important delivery boundary

This is a production-oriented HRMS foundation, not a claim that hardware integrations or jurisdiction-specific payroll calculations are complete. Fingerprint/face/RFID devices need vendor adapters. Tax, pension and statutory payroll rules must be configured and validated for each jurisdiction before live payroll use. The initial calculator creates employee payroll entries from protected base-salary values and deliberately marks the calculation component as `foundation_basic_salary_only`.

## Migration

```text
x7k1m3n5p680 -> y8m2n4p6q790 -> z9n3p5q7r800
```

The deployment image must contain both `y8m2n4p6q790` and `z9n3p5q7r800`.
