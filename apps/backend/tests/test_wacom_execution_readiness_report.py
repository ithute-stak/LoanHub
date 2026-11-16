"""Execution readiness is a read-only denial checklist, never a signing grant."""
from types import SimpleNamespace as R
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response

from routers import wacom_candidate_verification as routes


class Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def limit(self, count):
        return self

    def all(self):
        return self.rows


class DB:
    def __init__(self, challenges):
        self.challenges = challenges

    def query(self, model):
        return Query(self.challenges)


def context():
    company, contract_id, receipt_id = uuid4(), uuid4(), uuid4()
    contract = R(id=contract_id, company_id=company, status="draft",
                 borrower_signed_at=None)
    receipt = R(id=receipt_id, company_id=company, contract_id=contract_id,
                status="reserved", executed_file_id=uuid4())
    return company, contract, receipt


def run(monkeypatch, challenges=None, receipt_changes=None, contract_changes=None):
    company, contract, receipt = context()
    for key, value in (receipt_changes or {}).items():
        setattr(receipt, key, value)
    for key, value in (contract_changes or {}).items():
        setattr(contract, key, value)
    monkeypatch.setattr(routes, "require_tenant_roles", lambda *args: None)
    monkeypatch.setattr(routes, "_row",
                        lambda db, model, company_id, record_id:
                        contract if record_id == contract.id else
                        receipt if record_id == receipt.id else None)
    response = Response()
    result = routes.contract_execution_readiness(
        contract.id, receipt.id, response, DB(challenges or []),
        R(company_id=company))
    assert response.headers["cache-control"] == "no-store, private"
    assert result["contract_id"] == str(contract.id)
    assert result["receipt_id"] == str(receipt.id)
    assert result["execution_available"] is False
    return result["blockers"]


def test_no_challenge_denies_execution(monkeypatch):
    blockers = run(monkeypatch)
    assert "fresh_borrower_affirmation_not_recorded" in blockers
    assert "workstation_key_proof_not_recorded" in blockers
    assert "physical_stu540_attestation_not_implemented" in blockers
    assert "independent_legal_release_not_implemented" in blockers
    assert "atomic_execution_commit_not_implemented" in blockers


def test_key_and_borrower_proof_still_cannot_execute(monkeypatch):
    blockers = run(monkeypatch, [R(borrower_affirmed_at="present",
                                  workstation_proof_at="present")])
    assert "fresh_borrower_affirmation_not_recorded" not in blockers
    assert "workstation_key_proof_not_recorded" not in blockers
    assert "physical_stu540_attestation_not_implemented" in blockers
    assert "atomic_execution_commit_not_implemented" in blockers


def test_archived_candidate_required(monkeypatch):
    blockers = run(monkeypatch, receipt_changes={"executed_file_id": None})
    assert "archived_candidate_not_reserved" in blockers


def test_existing_signed_contract_never_reexecutes(monkeypatch):
    blockers = run(monkeypatch, contract_changes={"status": "signed"})
    assert "contract_already_signed_or_changed" in blockers


def test_multiple_challenges_fail_closed(monkeypatch):
    with pytest.raises(HTTPException) as error:
        run(monkeypatch, [R(), R()])
    assert error.value.status_code == 409


def test_no_mutation_or_legal_execution_in_readiness_handler():
    import inspect
    source = inspect.getsource(routes.contract_execution_readiness)
    for forbidden in ("db.commit(", "contract.status =", "borrower_signed_at =",
                      "execution_available\": True", "store_bytes("):
        assert forbidden not in source
