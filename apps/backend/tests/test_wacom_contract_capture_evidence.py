"""Contract-scoped Wacom evidence discovery never signs or reuses captures."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from routers import contract_email_otp as route


class Query:
    def __init__(self, records):
        self.records=records
        self.filters=[]
    def filter(self,*clauses):
        self.filters.extend(clauses)
        return self
    def order_by(self,*args):
        return self
    def limit(self,limit):
        assert limit==10
        return self
    def all(self):
        return self.records


class DB:
    def __init__(self,records):
        self.q=Query(records)
        self.commits=0
    def query(self,model):
        assert model is route.ManagedFile
        return self.q
    def commit(self):
        self.commits+=1


def setup(monkeypatch, signed=False, records=None):
    company_id=uuid4()
    borrower_id=uuid4()
    contract_id=uuid4()
    context=SimpleNamespace(company_id=company_id,user=SimpleNamespace(id=uuid4()))
    contract=SimpleNamespace(
        id=contract_id,borrower_id=borrower_id,
        borrower_signed_at=datetime.now(timezone.utc) if signed else None,
        locked_at=None,status="draft",pdf_file_id=uuid4(),
        contract_hash="f"*64,
    )
    monkeypatch.setattr(route,"require_tenant_roles",lambda *_:None)
    monkeypatch.setattr(route,"_contract",lambda *_args,**_kwargs:contract)
    return context,contract,DB(records or [])


def test_verified_capture_metadata_only_no_signing(monkeypatch):
    file_id=uuid4()
    row=SimpleNamespace(id=file_id,created_at=datetime.now(timezone.utc))
    context,contract,db=setup(monkeypatch,records=[row])
    result=route.contract_verified_capture_evidence(
        contract.id,db=db,context=context,
    )
    assert result["capture_evidence"]==[{
        "file_id":str(file_id),"captured_at":row.created_at.isoformat(),
        "evidence_status":"verified_capture",
    }]
    assert result["borrower_id"]==str(contract.borrower_id)
    assert result["requires_fresh_contract_consent"] is True
    assert result["requires_document_specific_authorization"] is True
    assert result["can_apply_capture_to_document"] is False
    assert result["automatic_signature_reuse_enabled"] is False
    assert result["contract_signed"] is False
    assert db.commits==0
    assert len(db.q.filters)>=8
    assert "signature_image" not in str(result)
    assert "storage_key" not in str(result)


def test_existing_signed_contract_does_not_reauthorize(monkeypatch):
    context,contract,db=setup(monkeypatch,signed=True)
    result=route.contract_verified_capture_evidence(contract.id,db=db,context=context)
    assert "borrower_already_signed" in result["document_preflight_blockers"]
    assert result["can_apply_capture_to_document"] is False


def test_missing_capture_still_requires_consent(monkeypatch):
    context,contract,db=setup(monkeypatch)
    result=route.contract_verified_capture_evidence(contract.id,db=db,context=context)
    assert result["capture_evidence"]==[]
    assert result["requires_fresh_contract_consent"] is True
    assert db.commits==0


def test_context_authorization_failure_stops_before_lookup(monkeypatch):
    context,contract,db=setup(monkeypatch)
    def denied(*args):
        raise HTTPException(403,"Not allowed")
    monkeypatch.setattr(route,"require_tenant_roles",denied)
    with pytest.raises(HTTPException) as error:
        route.contract_verified_capture_evidence(contract.id,db=db,context=context)
    assert error.value.status_code==403
    assert not db.q.filters


def test_endpoint_is_registered():
    from api.v1.router import api_router
    paths={r.path for r in api_router.routes}
    assert "/contract-signing/contracts/{contract_id}/pad/verified-capture-evidence" in paths
