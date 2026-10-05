from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class PolyglotBenchmarkRun(Base):
    __tablename__ = "polyglot_benchmark_runs"

    requested_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    iterations = Column(Integer, nullable=False)
    all_candidates = Column(Boolean, nullable=False, default=False, index=True)
    promotion_candidate_count = Column(Integer, nullable=False, default=0)
    summary = Column(String(255), nullable=False, default="")
    criteria = Column(JSONB, nullable=False, default=dict)
    results = Column(JSONB, nullable=False, default=list)
    routing_snapshot = Column(JSONB, nullable=False, default=dict)

    requested_by = relationship("User")
