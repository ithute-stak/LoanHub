"""Exercise *real service function bodies* behind permanently disabled public gates.

Compile a test-only function from the production AST without the first HTTP 503
raise. The exported production function is never changed or monkeypatched.
These are negative-path checks, not successful financial posting certification.
"""
import ast
import inspect
import textwrap
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services import final_installment_rollover_posting as transfer_service
from services import rollover_compensation_posting as reversal_service


def _test_only_disabled_body(module, function_name):
    original = getattr(module, function_name)
    tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
    fn = tree.body[0]
    assert isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
    first = fn.body[0]
    assert isinstance(first, ast.Raise), "Expected fail-closed 503 as first instruction"
    assert isinstance(first.exc, ast.Call)
    assert any(
        keyword.arg == "status_code"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value == 503
        for keyword in first.exc.keywords
    ), "Never bypass an unknown or missing financial safety gate"
    fn.body.pop(0)
    ast.fix_missing_locations(tree)
    scope = dict(vars(module))
    exec(compile(tree, inspect.getfile(original), "exec"), scope)
    return scope[function_name]


class Query:
    def filter(self, *args):
        return self
    def with_for_update(self):
        return self
    def one_or_none(self):
        return None


class MissingLoanSession:
    def __init__(self):
        self.queried = False
    def query(self, *args):
        self.queried = True
        return Query()
    def add(self, *_):
        raise AssertionError("No financial record may be written")
    def commit(self):
        raise AssertionError("No financial transaction may commit")


def test_actual_transfer_body_rejects_missing_parent_without_any_write():
    posting = _test_only_disabled_body(transfer_service, "post_final_rollover")
    db = MissingLoanSession()
    with pytest.raises(HTTPException) as exc:
        posting(
            db, company_id=uuid4(), parent_id=uuid4(), installment_id=uuid4(),
            approved_amount=Decimal("60"), due_date=date(2026, 12, 1),
            agreement_reference="AGREEMENT", approval_reference="APPROVAL",
            actor_user_id=uuid4(), actor_role="owner", as_of=date(2026, 10, 29),
        )
    assert exc.value.status_code == 404
    assert db.queried


def test_actual_reversal_body_rejects_nonindependent_approval_before_sql():
    compensation = _test_only_disabled_body(reversal_service, "post_rollover_compensation")
    maker = uuid4()
    db = MissingLoanSession()
    with pytest.raises(HTTPException) as exc:
        compensation(
            db, company_id=uuid4(), transfer_id=uuid4(), actor_user_id=maker,
            independent_approver_id=maker, reference="REF",
            approval_reference="APPROVAL", reason="Test",
        )
    assert exc.value.status_code == 409
    assert not db.queried


@pytest.mark.parametrize("module,name", [
    (transfer_service, "post_final_rollover"),
    (reversal_service, "post_rollover_compensation"),
])
def test_live_service_gate_still_returns_503(module, name):
    fn = getattr(module, name)
    assert isinstance(ast.parse(textwrap.dedent(inspect.getsource(fn))).body[0].body[0], ast.Raise)
