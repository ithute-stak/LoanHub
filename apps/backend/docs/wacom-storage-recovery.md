# Wacom PDF candidate recovery — operator checklist

This is a **read-only audit**, not a contract-signing or data-deletion tool.

From the backend working directory, with the same approved read-only PostgreSQL
credentials and storage configuration as the target environment:

```bash
python -m scripts.wacom_reconcile_storage \
  --company-id <approved-company-uuid> \
  --provider local
```

For S3/MinIO-backed installations use `--provider s3` (supported by the existing
S3 adapter). Do not supply real customer IDs in public CI logs or support tickets.
The command emits JSON and exits with status 2 if there are findings or
the storage inventory is incomplete.

## What it checks

- Approved tenant and storage namespace only.
- Candidate PDF file metadata and execution receipt references.
- Missing candidate storage objects where the inventory is complete.
- Unreferenced candidate file metadata older than the review threshold.
- Unattributed storage objects **without assuming they are Wacom evidence**.
- Digest disagreement between a receipt and its file metadata.

This does **not** read or expose PDF content. It does **not** certify the legal
validity of a signature. The separate archive-integrity endpoint checks
encrypted file contents and document hashes.

## Recovery policy

1. Run on a consistent database snapshot and a scoped storage inventory,
   ideally while new Wacom candidate writes are paused in the isolated staging
   environment. Without a consistent snapshot, findings may be transient.
2. Preserve storage objects and database snapshots before making any repairs.
3. Investigate each finding against the application audit log and original
   contract/consent records. Unattributed objects are never safe to delete
   automatically.
4. A completed PostgreSQL COMMIT with an uncertain network response must
   **not** be retried as a new signing operation; inspect the execution receipt
   and its candidate-file digest.
5. Record the investigation and obtain independent approval before any manual
   administrative cleanup. Do not change borrower signature timestamps.
6. Re-run the audit and the independent archive-integrity verifier after
   remediation.

## Limitations

A complete database snapshot and local/S3 object-list response are separate
systems, not an atomic cross-system snapshot. No cleanup, lease, scheduler,
automatic repair, or legally operative contract execution is implemented.
Physical STU-540 workstation signing tests and legal review are still required.

All Wacom signing and candidate-archive feature flags remain disabled by default.
