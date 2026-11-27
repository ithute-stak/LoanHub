"""Canonical evidence binding for a future authenticated review workflow.

A digest binds content; it does not authenticate the reviewer or the sources.
"""
import hashlib
import json
from dataclasses import asdict
from datetime import timezone
from decimal import Decimal
from uuid import UUID

from payment_engine.principal_x_bound_reconciliation import BoundLedgerReview
from payment_engine.principal_x_ledger_source_attestation import require_authoritative_ledger_attestations


def ledger_review_digest(review: BoundLedgerReview, *, maker_user_id: UUID,
                         review_reference: str) -> str:
    if not all(isinstance(value, UUID) for value in (
        review.company_id, review.loan_id, maker_user_id,
    )):
        raise ValueError("Verified review scope required")
    if not isinstance(review_reference, str) or not review_reference.strip() or len(review_reference) > 180:
        raise ValueError("Invalid review reference")
    if not isinstance(review.source_revision, str) or len(review.source_revision) != 64 or any(
        c not in "0123456789abcdef" for c in review.source_revision
    ):
        raise ValueError("Invalid financial revision")
    if review.reviewed_at.utcoffset() is None:
        raise ValueError("Timezone-aware evidence timestamp required")
    completeness = require_authoritative_ledger_attestations(
        net_collected=review.net_collected, attestations=review.attestations,
    )
    payload = {
        "version": 1,
        "company_id": str(review.company_id),
        "loan_id": str(review.loan_id),
        "maker_user_id": str(maker_user_id),
        "review_reference": review_reference,
        "source_revision": review.source_revision,
        "reviewed_at": review.reviewed_at.astimezone(timezone.utc).isoformat(),
        "net_collected": format(completeness.net_collected, ".2f"),
        "attestations": [asdict(row) for row in sorted(
            review.attestations, key=lambda row: row.source_family
        )],
    }
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")).hexdigest()
