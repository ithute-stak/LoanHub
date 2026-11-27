"""Exercise the internal approval lifecycle with synthetic financial evidence."""
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from database.models.enums import UserRole
from database.models.governance_control import ApprovalRequest
from database.models.principal_x_ledger_review import PrincipalXLedgerReview
from payment_engine.principal_x_bound_reconciliation import BoundLedgerReview
from payment_engine.principal_x_ledger_source_attestation import LedgerSourceAttestation, REQUIRED_SOURCE_FAMILIES
from services import principal_x_maker_submission as maker
from services import principal_x_checker_decision as checker
from services import principal_x_evidence_repository as repository


@pytest.fixture
def flow(monkeypatch):
    company, loan, maker_id, checker_id = (uuid4() for _ in range(4))
    def context(actor, role):
        return SimpleNamespace(company_id=company, branch_id=None, role=role,
                               user=SimpleNamespace(id=actor),
                               staff=SimpleNamespace(company_id=company, user_id=actor))
    state = SimpleNamespace(proposal=None, rows=[], revision="a" * 64)
    def execute(statement):
        entity = statement.column_descriptions[0]["entity"]
        if entity is ApprovalRequest:
            return SimpleNamespace(scalar_one_or_none=lambda: state.proposal)
        assert entity is PrincipalXLedgerReview
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: state.rows))
    def add(row):
        if isinstance(row, ApprovalRequest):
            if row.id is None:
                row.id = uuid4()
            state.proposal = row
        else:
            assert isinstance(row, PrincipalXLedgerReview)
            state.rows.append(row)
    db = SimpleNamespace(no_autoflush=nullcontext(), new=[], dirty=[], deleted=[],
                         execute=execute, add=add, flush=lambda: None,
                         expire_all=lambda: None)
    def reviewers(_db, *, company_id, maker_user_id, checker_user_id):
        assert company_id == company
        if maker_user_id != maker_id or checker_user_id != checker_id:
            raise ValueError("Independent authorized reviewers required")
    for module in (maker, checker):
        monkeypatch.setattr(module, "lock_financial_loan", lambda *a, **kw: None)
        monkeypatch.setattr(module, "require_independent_ledger_reviewers", reviewers)
        monkeypatch.setattr(module, "local_principal_x_source_revision",
                            lambda *a, **kw: state.revision)
    review = BoundLedgerReview(
        company_id=company, loan_id=loan, source_revision=state.revision,
        reviewed_at=datetime.now(timezone.utc), net_collected=Decimal("696.00"),
        attestations=tuple(LedgerSourceAttestation(family, True, "cert:" + family, 0)
                           for family in sorted(REQUIRED_SOURCE_FAMILIES)),
    )
    return SimpleNamespace(db=db, state=state, company=company, loan=loan,
                           maker_id=maker_id, checker_id=checker_id, review=review,
                           maker_context=context(maker_id, UserRole.FINANCE_OFFICER),
                           checker_context=context(checker_id, UserRole.AUDITOR))


def submit(flow, **overrides):
    args = dict(context=flow.maker_context, loan_id=flow.loan,
                checker_user_id=flow.checker_id, review_reference="TEST-REVIEW",
                trusted_review=flow.review, max_age=timedelta(minutes=5))
    args.update(overrides)
    return maker.submit_ledger_review(flow.db, **args)


def decide(flow, **overrides):
    proposal = flow.state.proposal
    args = dict(context=flow.checker_context, loan_id=flow.loan,
                approval_id=proposal.id, expected_digest=proposal.payload["evidence_digest"],
                approved=True, reason="Independent evidence review completed",
                max_age=timedelta(minutes=5))
    args.update(overrides)
    return checker.decide_ledger_review(flow.db, **args)


def read(flow):
    return repository.read_approved_local_review(
        flow.db, company_id=flow.company, loan_id=flow.loan,
        source_revision=flow.state.revision,
    )


def test_complete_lifecycle(flow):
    proposal = submit(flow)
    assert proposal.status == "pending"
    assert read(flow) is None
    assert submit(flow) is proposal
    assert decide(flow).status == "approved"
    assert len(flow.state.rows) == 1
    assert read(flow) == flow.review
    with pytest.raises(ValueError, match="no longer pending"):
        decide(flow)
    assert len(flow.state.rows) == 1


def test_rejected_review_creates_no_evidence(flow):
    submit(flow)
    assert decide(flow, approved=False).status == "rejected"
    assert read(flow) is None


def test_stale_revision_blocks_approval(flow):
    proposal = submit(flow)
    flow.state.revision = "b" * 64
    with pytest.raises(ValueError, match="stale"):
        decide(flow)
    assert proposal.status == "pending"
    assert not flow.state.rows


def test_changed_evidence_blocks_approval(flow):
    proposal = submit(flow)
    proposal.payload["net_collected"] = "697.00"
    with pytest.raises(ValueError, match="digest mismatch"):
        decide(flow)
    assert not flow.state.rows


def test_wrong_checker_blocks_approval(flow):
    submit(flow)
    with pytest.raises(ValueError):
        decide(flow, context=flow.maker_context)
    assert not flow.state.rows


def test_conflicting_reference_blocks_resubmission(flow):
    from dataclasses import replace
    submit(flow)
    with pytest.raises(ValueError, match="different evidence"):
        submit(flow, trusted_review=replace(flow.review, net_collected=Decimal("697.00")))


@pytest.mark.parametrize("field,value", [("status", "rejected"), ("decision_reason", ""), ("decided_by_user_id", None)])
def test_inconsistent_approval_blocks_reader(flow, field, value):
    submit(flow)
    proposal = decide(flow)
    setattr(proposal, field, value)
    with pytest.raises(ValueError, match="decision missing or inconsistent"):
        read(flow)


def test_ambiguous_immutable_reviews_block_reader(flow):
    submit(flow)
    decide(flow)
    flow.state.rows.append(flow.state.rows[0])
    with pytest.raises(ValueError, match="Ambiguous"):
        read(flow)
