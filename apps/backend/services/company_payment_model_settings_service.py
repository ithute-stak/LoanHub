"""Read-only company payment policy loader.

Requires the dedicated table migration and ORM registration before use.
Writing settings must be restricted to authenticated company administrators.
"""
from sqlalchemy.orm import Session

from database.models.company_payment_model_settings import CompanyPaymentModelSettings
from payment_engine.principal_x_company_policy_record import (
    CompanyPaymentPolicyRecord, parse_company_payment_policy,
)


def read_company_payment_policy(
    db: Session, *, company_id: str
) -> CompanyPaymentPolicyRecord:
    if not company_id or not str(company_id).strip():
        raise ValueError("Company ID is required")
    row = (
        db.query(CompanyPaymentModelSettings)
        .filter(CompanyPaymentModelSettings.company_id == company_id)
        .one_or_none()
    )
    if row is None:
        return parse_company_payment_policy(company_id=str(company_id), stored=None)
    return parse_company_payment_policy(
        company_id=str(company_id),
        stored={
            "default_model": row.default_model,
            "allow_new_loans": row.allow_new_loans,
            "enable_live_collections": row.enable_live_collections,
        },
    )
