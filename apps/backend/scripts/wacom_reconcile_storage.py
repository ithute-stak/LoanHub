"""Read-only Wacom tenant storage reconciliation.

Run from apps/backend:
  python -m scripts.wacom_reconcile_storage --company-id UUID --provider local

This command intentionally cannot delete files or update contract state.
Use a non-production replica for broad audits where possible.
"""
from __future__ import annotations

import argparse
import json
from uuid import UUID

from database.models.file_management import ManagedFile
from database.models.wacom_execution_receipt import WacomExecutionReceipt
from database.session import SessionLocal
from services.object_storage_service import get_storage
from services.wacom_storage_reconciliation import reconcile_wacom_candidates


def inventory_for_company(*, storage, company_id, max_records=10000):
    """Return keys and a completeness flag; never infer missing objects from partial data."""
    prefix = str(company_id) + "/"
    if storage.provider == "local":
        folder = storage._path(str(company_id))
        if not folder.is_dir():
            return [], True
        keys = []
        for item in folder.rglob("*"):
            # Symlinks and unexpected paths are not trustworthy inventory entries.
            if item.is_symlink():
                return keys, False
            if not item.is_file():
                continue
            resolved = item.resolve()
            if folder.resolve() not in resolved.parents:
                return keys, False
            keys.append(str(resolved.relative_to(storage.root)).replace("\\", "/"))
            if len(keys) > max_records:
                return keys[:max_records], False
        return sorted(keys), True
    if storage.provider == "s3":
        # Prefix is rooted in the storage provider's configured bucket prefix.
        query = {"Bucket": storage.bucket, "Prefix": storage._key(str(company_id)) + "/"}
        keys = []
        while True:
            reply = storage.client.list_objects_v2(**query)
            for obj in reply.get("Contents", []):
                object_key = obj["Key"]
                configured = storage.prefix + "/" if storage.prefix else ""
                if not object_key.startswith(configured):
                    raise ValueError("S3 object unexpectedly outside configured prefix")
                key = object_key[len(configured):]
                if not key.startswith(prefix):
                    raise ValueError("S3 object unexpectedly outside tenant prefix")
                keys.append(key)
                if len(keys) > max_records:
                    return keys[:max_records], False
            if not reply.get("IsTruncated"):
                return sorted(keys), True
            continuation = reply.get("NextContinuationToken")
            if not continuation:
                return keys, False
            query["ContinuationToken"] = continuation
    raise ValueError("Only explicitly selected local and s3 inventory supported")


def audit(*, company_id, provider, limit=10000):
    if not 1 <= limit <= 10000:
        raise ValueError("Inventory limit must be between 1 and 10000")
    with SessionLocal() as db:
        files = (db.query(ManagedFile)
                 .filter(ManagedFile.company_id == company_id)
                 .limit(limit + 1).all())
        receipts = (db.query(WacomExecutionReceipt)
                    .filter(WacomExecutionReceipt.company_id == company_id)
                    .limit(limit + 1).all())
        if len(files) > limit or len(receipts) > limit:
            raise ValueError("Database tenant snapshot exceeds limit; cannot certify completeness")
        if any((file.storage_provider or "local").lower() != provider for file in files):
            raise ValueError("Mixed storage providers require separate, manually reviewed snapshots")
        keys, complete = inventory_for_company(
            storage=get_storage(provider), company_id=company_id,
            max_records=limit,
        )
        result = reconcile_wacom_candidates(
            company_id=company_id, managed_files=files, receipts=receipts,
            storage_keys=keys, inventory_complete=complete,
            max_records=limit,
        )
        return {
            "company_id": str(company_id),
            "provider": provider,
            "inventory_complete": complete,
            "managed_files_examined": len(files),
            "receipts_examined": len(receipts),
            "objects_examined": len(keys),
            "findings": [finding.__dict__ for finding in result],
            "read_only": True,
            "contract_signed": False,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company-id", required=True, type=UUID)
    parser.add_argument("--provider", required=True, choices=("local", "s3"))
    parser.add_argument("--max-records", type=int, default=10000)
    args = parser.parse_args()
    result = audit(
        company_id=args.company_id, provider=args.provider,
        limit=args.max_records,
    )
    print(json.dumps(result, sort_keys=True))
    if result["findings"] or not result["inventory_complete"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
