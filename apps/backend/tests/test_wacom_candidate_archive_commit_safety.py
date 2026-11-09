"""Fail-closed Wacom candidate archive commit-time expiry and cleanup checks."""
import inspect
from types import SimpleNamespace

from routers import wacom_pdf_candidates as routes


def test_candidate_archive_uses_fresh_commit_timestamp():
    code = inspect.getsource(routes.archive_pdf_candidate)
    assert "commit_now = datetime.now(timezone.utc)" in code
    assert "reserved_at=commit_now" in code
    assert "candidate_sha256=digest, now=commit_now" in code
    assert "expiry <= datetime.now(timezone.utc)" in code
    assert code.index("expiry <= datetime.now(timezone.utc)") < code.index("db.commit()")


def test_cleanup_deletes_only_named_object(monkeypatch):
    deleted = []
    class Storage:
        def delete(self, key):
            deleted.append(key)
    monkeypatch.setattr(routes, "get_storage", lambda provider: Storage())
    routes._cleanup_failed_candidate(
        SimpleNamespace(storage_provider="local", storage_key="company/synthetic.bin")
    )
    assert deleted == ["company/synthetic.bin"]


def test_cleanup_does_not_mask_original_failure(monkeypatch):
    class Storage:
        def delete(self, key):
            raise OSError("simulated storage outage")
    monkeypatch.setattr(routes, "get_storage", lambda provider: Storage())
    # Best effort: caller preserves earlier DB rollback reason.
    routes._cleanup_failed_candidate(
        SimpleNamespace(storage_provider="s3", storage_key="company/synthetic.bin")
    )


def test_no_commit_failure_cleanup_for_uncertain_outcome():
    code = inspect.getsource(routes.archive_pdf_candidate)
    # Only explicit IntegrityError is treated as a definitive rejected commit.
    assert "except IntegrityError as exc:" in code
    assert "except Exception" not in code[code.index("    try:\n        db.commit()"):]


def test_does_not_mark_contract_signed():
    code = inspect.getsource(routes)
    assert "contract.borrower_signed_at =" not in code
    assert "contract.status =" not in code
    assert "authorization.consumed_at =" not in code
