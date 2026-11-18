# Phase 80 — Global historical passport collision protection

A client can register with a passport when no national ID is supplied.
Legacy loan captures may also hold a passport without a national ID.

The earlier new-only registration guard checked legacy national IDs but did
not consistently compare historical passports. This could allow a passport
matching a historical capture in a different company to pass that portion
of pre-registration screening.

Phase 80 adds global, aggregate-only checks against both
`legacy_loan_captures.national_id` and `legacy_loan_captures.passport_number`
in the guard and atomic registration service. No client IDs, matched
accounts or historical data are returned to the requester.

New tests cover passport-only legacy collision rejection and, in actual
isolated PostgreSQL, prove a cross-company historical passport entry blocks
new-only creation without changing its status or financial amounts.

The API and Batlokoa registration feature remain disabled. No production
migrations, indexes, client records or loan data are modified.
