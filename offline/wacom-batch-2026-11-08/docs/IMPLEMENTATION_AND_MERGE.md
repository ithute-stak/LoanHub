# One-batch remaining implementation and merge instructions

## Existing baseline (do not rewrite)

- LoanHub username/password authentication and membership checks.
- First-party Ed25519 workstation enrollment and two-person approval.
- Shared-PC employee assignment and local Go switch-operator UI.
- Challenge/proof exchange, hashed 5-minute backend sessions, renewal.
- Quarantined STU-540 capture and independent evidence review.
- Server-side session revocation on logout and management revocation.

## Batch integration checklist

1. Verify `main` commit includes PR #631 (`ca8e723c0912ae96b13dc616b124c19582e3ea2c`), and whether pending PR #632 is already merged. Patcher accommodates either.
2. Use the patcher's dry run against a clean Git checkout, then apply locally.
3. Review Alembic heads; migration `d3e4f5a6b845` relies on `c2d3e4f5g834`. Validate existing LoanContract relationships and PDF stored digest against a disposable staging database before deployment.
4. Review and test the included **local UI patch** for per-document consent with existing physical STU-540 callback. Ensure the exact PDF is visible to the borrower; the UI currently shows its hash and depends on viewing the contract in LoanHub separately.
5. Add pre-enrollment and employee assignment administration to your existing LoanHub company portal.
6. Execute complete Go test suite and backend test suite with PostgreSQL, including migration upgrade + downgrade on disposable DB.
7. Test branch assignment and company isolation, different IP addresses, authorization refresh after revoked employee, replayed challenge and clock drift.
8. Deploy a dedicated staging stack only, with test-only company/employee/borrower and test contract PDF, never real customer data.
9. Configure only the staging backend with both `LOANHUB_WACOM_REQUIRE_BRIDGE_SESSION=1` and `LOANHUB_WACOM_DOCUMENT_INTENTS_ENABLED=1`, and only local staging PC with `LOANHUB_WACOM_PC_STRICT=1` plus private key directory.
10. Verify explicit authorization for each separate document; attach its precise SHA-256 and version to a fresh signer confirmation. The evidence review step never directly triggers final PDF signing.
11. Have a separate security reviewer sign off on logs, rollback, deployment isolation and abuse protections before opening one integration PR to merge.
12. No real financial operations or PDF signing without separate integration to LoanHub's existing contract signing domain, legal approval and an independent signature verification strategy.

## Deferred merge command (do not automate)

```bash
git switch -c feat/wacom-offline-completion-batch
python3 /path/to/bundle/apply_offline.py --repo . --apply
# run tests, migrations on disposable DB, and inspect git diff
git add apps/backend services/wacom-connector
git commit -m 'Complete Wacom first-party PC document evidence engineering batch'
git push -u origin feat/wacom-offline-completion-batch
# Open one PR, wait for green checks, review and only then merge.
```

## Pending functionality beyond this batch

The official STU-540 SDK must be exercised on an actual Linux/Windows workstation to verify stroke timestamps, physical pen packets, capture framing, buffer cleanup, and signature-to-browser previews. A legally operative document-signing and certified PDF output layer is **not** implemented here: the system stores verified evidence to be explicitly approved and bound to a document in a later integration. False claims that saved operator signatures authorize all future documents are prohibited.
