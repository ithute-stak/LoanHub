# Phase 38–44 offline source integration

This directory preserves the original **offline Phase 38–44 development
bundle** in LoanHub, as source and tests. It is a **reference-only archive**,
not an active payment integration or deployable financial processor.

- Original Phase 35 preview code and its adapted reference files were
  previously merged into LoanHub through PRs #610–#612 and are not duplicated
  here. The original archive's installer must not overwrite newer main code.
- The 58 source and documentation files in this folder are copied from the
  Phase 44 offline package (including its original README and checksums).
- The original `phase44/coordinator.py` uses synthetic SQLite storage and
  synthetic provider attestations. **Never connect it to payment APIs**.
- The `schemas/*.sql` files are design/test artifacts, **not migrations**.
- `ci_templates/*.yml` are archived examples, not deployed Actions workflows.
- The active CI workflow runs isolated regression tests without contacting
  payment providers or production databases.
- The three optional PostgreSQL tests skip without an explicit disposable
  test database, so a green offline CI is not PostgreSQL certification.

## Test locally

```bash
cd docs/reference/batlokoa_phases38_44
python3 run_all_tests.py
```

Expected from the original source bundle: 159 passing, 3 skipped (162 total).

## Remaining engineering work

A real transaction processor still needs reviewed LoanHub and IthutePay
database mappings, approved migrations and RLS, verified borrower mandates,
provider-specific documented callback authentication, actual provider
settlement reconciliation, atomic journal posting and operational rollback.
Keep all financial execution disabled until authorized and certified.

**Preserve the existing direct Vodacom M-PESA integration and shortcode
38542; Golink remains optional and replaceable.** No production deployment,
live financial activity, merchant configuration or provider credentials are
changed by this pull request.
