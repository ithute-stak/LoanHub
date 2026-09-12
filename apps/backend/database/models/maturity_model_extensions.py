"""Small mapped-column extensions used by maturity/recovery workflows.

CollectionCase predates the maturity feature. Keeping the action-claim columns
here avoids duplicating the large lending-operations model while still mapping
migration-owned columns onto the existing declarative class.
"""

from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from database.models.lending_operations import CollectionCase


if not hasattr(CollectionCase, "action_claimed_by_user_id"):
    CollectionCase.action_claimed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    CollectionCase.action_claimed_at = Column(DateTime, nullable=True)
    CollectionCase.action_claim_expires_at = Column(DateTime, nullable=True, index=True)
