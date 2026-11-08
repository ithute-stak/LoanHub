# LoanHub Wacom — Expanded Offline Engineering Source Bundle

**Consolidated offline code** for the existing LoanHub first-party shared-PC STU-540 project. It includes the new document-intent backend, PostgreSQL migration, Go client and localhost UI integration patches, server/session hardening, policy tests, offline Go harness and staging acceptance tools.

This is substantially larger than the earlier nine-file security patch ZIP, but **not a claim that every end-to-end feature is complete**. The real STU-540 capture implementation remains in the LoanHub repository; actual device testing, contract PDF execution and deployment require verified integration.

Start with [docs/README.md](docs/README.md) and [docs/IMPLEMENTATION_AND_MERGE.md](docs/IMPLEMENTATION_AND_MERGE.md).

```bash
bash tools/run_offline_tests.sh
bash tools/test_go_isolated.sh
python3 tools/offline_acceptance.py
python3 apply_offline.py --repo /absolute/path/to/LoanHub
# After reviewing the dry-run diff:
python3 apply_offline.py --repo /absolute/path/to/LoanHub --apply
```

Never enable production signing on the strength of an offline package or a green unit test alone.
