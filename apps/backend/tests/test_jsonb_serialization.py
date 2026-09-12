import json
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from database.session import json_serializer


def test_json_serializer_handles_top_up_financial_snapshot_types():
    loan_id = uuid4()
    checked_at = datetime(2026, 8, 9, 15, 50, tzinfo=timezone.utc)

    encoded = json_serializer(
        {
            "paid_percent": Decimal("75.000"),
            "required_paid_percent": Decimal("75.000"),
            "loan": {
                "id": loan_id,
                "balance": Decimal("1250.50"),
            },
            "due_date": date(2026, 9, 30),
            "checked_at": checked_at,
        }
    )
    payload = json.loads(encoded)

    assert payload["paid_percent"] == "75.000"
    assert payload["required_paid_percent"] == "75.000"
    assert payload["loan"]["id"] == str(loan_id)
    assert payload["loan"]["balance"] == "1250.50"
    assert payload["due_date"] == "2026-09-30"
    assert payload["checked_at"] == checked_at.isoformat()


def test_json_serializer_still_rejects_unknown_objects():
    class Unsupported:
        pass

    with pytest.raises(TypeError):
        json_serializer({"unsupported": Unsupported()})
