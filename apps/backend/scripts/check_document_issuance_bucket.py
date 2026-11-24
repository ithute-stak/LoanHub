"""Read-only staging S3 Object Lock preflight, never creates or deletes data.

Usage (from apps/backend):
  python scripts/check_document_issuance_bucket.py --bucket YOUR_STAGING_BUCKET

Requires the AWS SDK's usual external credential chain. Avoid sharing output
containing the bucket identifier if its name is sensitive. This script does
NOT certify write restrictions, exact-version reads or retention survival.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import boto3
from botocore.config import Config

from services.document_issuance_bucket_preflight import inspect_locked_bucket_read_only


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only locked PDF bucket preflight")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()
    client = boto3.client("s3", region_name=args.region,
                          config=Config(connect_timeout=5, read_timeout=10, retries={"max_attempts": 2}))
    outcome = inspect_locked_bucket_read_only(client=client, bucket=args.bucket)
    print(json.dumps({
        "bucket": outcome.bucket, "ready": outcome.ready,
        "issues": list(outcome.issues),
        "mode": "read_only_configuration_inspection",
        "production_certified": False,
    }, sort_keys=True))
    return 0 if outcome.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
