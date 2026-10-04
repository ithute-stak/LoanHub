from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from services.credit_bureau_policy_service import experian_required_for_application


def _application(*, amount: str = "1000", product_id=None):
    return SimpleNamespace(
        requested_amount=Decimal(amount),
        product_id=product_id,
    )


def test_optional_never_requires_experian():
    app = _application()
    policy = {"requirement_mode": "optional"}

    assert experian_required_for_application(policy, app, stage="affordability") is False
    assert experian_required_for_application(policy, app, stage="approval") is False


def test_before_affordability_also_protects_approval():
    app = _application()
    policy = {"requirement_mode": "before_affordability"}

    assert experian_required_for_application(policy, app, stage="affordability") is True
    assert experian_required_for_application(policy, app, stage="approval") is True


def test_before_approval_does_not_block_affordability():
    app = _application()
    policy = {"requirement_mode": "before_approval"}

    assert experian_required_for_application(policy, app, stage="affordability") is False
    assert experian_required_for_application(policy, app, stage="approval") is True


def test_amount_threshold_only_applies_at_approval():
    app = _application(amount="7000")
    policy = {"requirement_mode": "amount_threshold", "required_above_amount": 5000}

    assert experian_required_for_application(policy, app, stage="affordability") is False
    assert experian_required_for_application(policy, app, stage="approval", amount=Decimal("4999.99")) is False
    assert experian_required_for_application(policy, app, stage="approval", amount=Decimal("5000")) is True
    assert experian_required_for_application(policy, app, stage="approval", amount=Decimal("7000")) is True


def test_selected_products_only_require_matching_product_at_approval():
    selected = uuid4()
    other = uuid4()
    app = _application(product_id=selected)
    policy = {
        "requirement_mode": "selected_products",
        "required_product_ids": [str(selected)],
    }

    assert experian_required_for_application(policy, app, stage="affordability") is False
    assert experian_required_for_application(policy, app, stage="approval") is True
    assert experian_required_for_application(policy, app, stage="approval", product_id=other) is False
