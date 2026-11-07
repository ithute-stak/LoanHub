# Wacom Phase 21 — real FastAPI contract conformance

The API smoke harness must match actual LoanHub endpoint paths, methods, authentication response shape and capture receipt status before any tests contact an approved isolated HTTPS backend.

Tests check the **real imported** LoginRequest, LoginResponse, AuthMembershipRead, AuthUserRead, API router path/method declarations and signature PNG parser. They also simulate login with inactive or wrong-company membership and ensure the synthetic test client refuses to adopt a bearer token.

Run from `apps/backend`:

```bash
python -m pytest -q tests/test_wacom_api_contract_conformance.py tests/test_wacom_real_api_smoke.py
```

This suite is offline and uses no real borrower data, actual Wacom scribbles or payment integration.

## Important follow-up gate

Passing conformance does not establish TLS reachability, the actual staging login, tenant-scoped reviewer access, encrypted storage, scanner readiness or successful physical PC data upload. Those require a separately isolated, approved LoanHub staging backend and synthetic accounts.

Do not deploy any draft PR to production. Review and integrate the stacked branches before staging testing. Never allow pending or reviewed handwriting evidence to authorize document signing on its own.