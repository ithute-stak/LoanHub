from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database.base import Base


class AIIntelligenceRun(Base):
    """One reproducible intelligence pass over company operational evidence."""

    __tablename__ = "ai_intelligence_runs"
    __table_args__ = (
        UniqueConstraint("company_id", "run_reference", name="uq_ai_intelligence_run_reference"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    run_reference = Column(String(100), nullable=False, index=True)
    run_type = Column(String(40), nullable=False, default="on_demand", index=True)
    status = Column(String(30), nullable=False, default="running", index=True)
    model_version = Column(String(80), nullable=False, default="explainable-v1")
    evidence_cutoff_at = Column(DateTime, nullable=False)
    insight_count = Column(Integer, nullable=False, default=0)
    critical_count = Column(Integer, nullable=False, default=0)
    high_count = Column(Integer, nullable=False, default=0)
    medium_count = Column(Integer, nullable=False, default=0)
    low_count = Column(Integer, nullable=False, default=0)
    summary = Column(JSONB, nullable=False, default=dict)
    triggered_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)


class AIIntelligenceInsight(Base):
    """Explainable decision-support insight. It never changes a loan or approval state."""

    __tablename__ = "ai_intelligence_insights"
    __table_args__ = (
        UniqueConstraint("run_id", "fingerprint", name="uq_ai_intelligence_run_fingerprint"),
    )

    run_id = Column(UUID(as_uuid=True), ForeignKey("ai_intelligence_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    insight_type = Column(String(60), nullable=False, index=True)
    domain = Column(String(40), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="medium", index=True)
    confidence_percent = Column(Numeric(6, 2), nullable=False, default=0)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    folio_number = Column(String(40), nullable=True, index=True)
    title = Column(String(240), nullable=False)
    explanation = Column(Text, nullable=False)
    recommended_action = Column(Text, nullable=False)
    rationale = Column(JSONB, nullable=False, default=list)
    evidence = Column(JSONB, nullable=False, default=dict)
    fingerprint = Column(String(64), nullable=False)
    status = Column(String(30), nullable=False, default="open", index=True)
    reviewed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    feedback = Column(String(30), nullable=True)
    feedback_note = Column(Text, nullable=True)


class AIIntelligenceGuardrailEvent(Base):
    """Audit evidence that intelligence remained advisory and human-controlled."""

    __tablename__ = "ai_intelligence_guardrail_events"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    insight_id = Column(UUID(as_uuid=True), ForeignKey("ai_intelligence_insights.id", ondelete="CASCADE"), nullable=True, index=True)
    event_type = Column(String(60), nullable=False, index=True)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    detail = Column(JSONB, nullable=False, default=dict)
    occurred_at = Column(DateTime, nullable=False)
