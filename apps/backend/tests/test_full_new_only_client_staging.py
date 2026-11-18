"""Phase 85 internal staging contract (no route, no commit)."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from database.models.enums import EmploymentStatus, Gender
from database.schemas.full_new_only_client_capture import FullNewOnlyClientCapture
from services.full_new_only_client_staging import (
    FullNewOnlyStagingUnavailable,
    _reject_unsafe_fields,
    stage_full_new_only_client_details,
)
from services.new_only_client_staging import StagedNewClient


def request(**updates):
    data = {
        "branch_id": uuid4(),
        "phone": "59000001",
        "first_name": "Palesa",
        "last_name": "Mokoena",
        "middle_name": "K",
        "gender": Gender.FEMALE,
        "date_of_birth": date(1990, 5, 1),
        "national_id": "SYNTH-REG-85",
        "district": "Maseru",
        "town_or_village": "Roma",
        "physical_address": "Synthetic residence",
        "employment_status": EmploymentStatus.EMPLOYED,
        "employment_type": "permanent",
        "employer_name": "Synthetic Employer",
        "monthly_income": Decimal("6400"),
        "income_day": 25,
        "job_title": "Clerk",
        "salary_date": "25",
        "consent_to_share_profile": False,
        "consent_to_credit_checks": True,
    }
    data.update(updates)
    return FullNewOnlyClientCapture.model_validate(data)


def staged_ids(branch):
    return StagedNewClient(
        user_id=uuid4(), borrower_id=uuid4(),
        client_account_id=uuid4(), company_id=uuid4(),
        branch_id=branch,
    )


@pytest.mark.parametrize("changes", [
    {"email": "somebody@example.org"},
    {"temporary_password": "test-only-not-a-real-password"},
    {"employer_group_id": uuid4()},
    {"cdas_employee_number": "SYNTH-EMP-001"},
    {"has_existing_loans": True, "existing_loan_total": Decimal("100")},
    {"has_existing_loans": True, "existing_loan_total": Decimal("50"),
     "external_debts": [{
         "creditor": "Synthetic creditor", "current_balance": Decimal("100"),
         "installment_amount": Decimal("10"),
         "total_installments": 10, "installments_paid": 0,
     }]},
    {"has_existing_loans": True, "existing_loan_total": Decimal("100"),
     "external_debts": [{
         "creditor": "Synthetic creditor", "current_balance": Decimal("100"),
         "installment_amount": Decimal("10"), "is_verified": True,
         "total_installments": 10, "installments_paid": 0,
     }]},
])
def test_unsupported_or_conflicting_capture_fails_before_mutation(changes):
    with pytest.raises(FullNewOnlyStagingUnavailable):
        _reject_unsafe_fields(request(**changes))


def test_explicit_activation_and_postgres_transaction_required():
    payload = request()
    stage = staged_ids(payload.branch_id)
    db = MagicMock()
    with pytest.raises(FullNewOnlyStagingUnavailable, match="disabled"):
        stage_full_new_only_client_details(
            db, payload=payload, staged=stage, actor_user_id=uuid4())
    db.query.assert_not_called()

    db.get_bind.return_value.dialect.name = "sqlite"
    db.in_transaction.return_value = True
    with pytest.raises(FullNewOnlyStagingUnavailable, match="PostgreSQL"):
        stage_full_new_only_client_details(
            db, payload=payload, staged=stage, actor_user_id=uuid4(),
            approved_internal_call=True)
    db.query.assert_not_called()


def test_scope_mismatch_rejected_without_profile_modification():
    payload = request()
    stage = staged_ids(payload.branch_id)
    db = MagicMock()
    db.get_bind.return_value.dialect.name = "postgresql"
    db.in_transaction.return_value = True
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    with pytest.raises(FullNewOnlyStagingUnavailable, match="scope"):
        stage_full_new_only_client_details(
            db, payload=payload, staged=stage,
            actor_user_id=uuid4(), approved_internal_call=True)
    db.flush.assert_not_called()


def test_stages_only_new_profile_fields_and_delegates_encrypted_banking_and_debts():
    payload = request()
    stage = staged_ids(payload.branch_id)
    actor = uuid4()
    db = MagicMock()
    db.get_bind.return_value.dialect.name = "postgresql"
    db.in_transaction.return_value = True
    person = SimpleNamespace()
    borrower = SimpleNamespace()
    db.query.return_value.filter.return_value.one_or_none.side_effect = [
        SimpleNamespace(source="new_only_registration"), person, borrower,
    ]
    with patch(
        "services.full_new_only_client_staging._save_assisted_banking_profile"
    ) as bank, patch(
        "services.full_new_only_client_staging.save_assisted_external_debts"
    ) as debts:
        stage_full_new_only_client_details(
            db, payload=payload, staged=stage,
            actor_user_id=actor, approved_internal_call=True)
    assert person.middle_name == "K"
    assert person.town_or_village == "Roma"
    assert person.physical_address == "Synthetic residence"
    assert borrower.employer_name == "Synthetic Employer"
    assert borrower.monthly_income == Decimal("6400")
    assert borrower.income_day == 25
    bank.assert_called_once()
    debts.assert_called_once()
    assert bank.call_args.kwargs["company_id"] == stage.company_id
    assert debts.call_args.kwargs["borrower"] is borrower
    db.flush.assert_called_once()
    db.commit.assert_not_called()
