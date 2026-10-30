"""Execute actual disabled rollover service body through accounting pre-commit guard.

Test-only AST extraction removes the public 503 and replaces the final commit
with a sentinel. This cannot activate the exported production entrypoint.
"""
import ast
import inspect
import textwrap
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
from datetime import date

import pytest

from services import final_installment_rollover_posting as service


class StopBeforeCommit(Exception):
    pass


def test_accounting_guard_must_run_before_any_rollover_commit():
    tree = ast.parse(textwrap.dedent(inspect.getsource(service.post_final_rollover)))
    fn = tree.body[0]
    assert isinstance(fn.body[0], ast.Raise)
    fn.body.pop(0)  # isolate from live 503 only in the compiled test function
    commits = [i for i, node in enumerate(fn.body) if isinstance(node, ast.Expr)
               and isinstance(node.value, ast.Call)
               and isinstance(node.value.func, ast.Attribute)
               and node.value.func.attr == "commit"]
    reconciles = [i for i, node in enumerate(fn.body) if isinstance(node, ast.Expr)
                  and isinstance(node.value, ast.Call)
                  and isinstance(node.value.func, ast.Name)
                  and node.value.func.id == "reconcile_rollover_accounting"]
    assert len(commits) == len(reconciles) == 1
    assert reconciles[0] < commits[0], "Accounting check must precede financial commit"
    fn.body[commits[0]] = ast.Raise(exc=ast.Call(
        func=ast.Name(id="StopBeforeCommit", ctx=ast.Load()), args=[], keywords=[]),
        cause=None)
    ast.fix_missing_locations(tree)
    scope = dict(vars(service), StopBeforeCommit=StopBeforeCommit)
    exec(compile(tree, inspect.getfile(service.post_final_rollover), "exec"), scope)
    assert scope["post_final_rollover"] is not service.post_final_rollover
    # Verify the exported service stays fail-closed even after test compilation.
    with pytest.raises(Exception) as exc:
        service.post_final_rollover(
            None, company_id=uuid4(), parent_id=uuid4(),
            installment_id=uuid4(), approved_amount=Decimal("60"),
            due_date=date(2026, 12, 1), agreement_reference="AGREEMENT",
            approval_reference="APPROVAL", actor_user_id=uuid4(),
            actor_role="owner", as_of=date(2026, 10, 30))
    assert getattr(exc.value, "status_code", None) == 503
