from __future__ import annotations

import sys
import uuid
from pathlib import Path

from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database.models.company import LoanCompany
from database.models.company_operations_phase1 import CRMRelationshipCase
from database.models.company_client import CompanyBorrowerAccount
from database.models.enums import CompanyStatus, EmploymentStatus, InstitutionType, UserRole
from database.models.borrower import Borrower
from database.models.user import User
from database.session import SessionLocal


PROBE_ROLE = "loanhub_rls_probe"


def _seed_company(db, suffix: str) -> LoanCompany:
    company = LoanCompany(
        name=f"RLS Probe Company {suffix} {uuid.uuid4().hex[:8]}",
        institution_type=InstitutionType.LOAN_COMPANY,
        phone=f"+2665{uuid.uuid4().int % 10_000_000:07d}",
        status=CompanyStatus.APPROVED,
        is_active=True,
    )
    db.add(company)
    db.flush()
    return company


def _seed_borrower(db, suffix: str) -> Borrower:
    user = User(
        phone=f"+2666{uuid.uuid4().int % 10_000_000:07d}",
        email=f"rls-{suffix}-{uuid.uuid4().hex[:8]}@example.invalid",
        password_hash="ci-only-not-a-real-password-hash",
        role=UserRole.BORROWER,
        is_active=True,
        is_verified=True,
        must_change_password=False,
    )
    db.add(user)
    db.flush()
    borrower = Borrower(
        user_id=user.id,
        employment_status=EmploymentStatus.EMPLOYED,
        other_monthly_income=0,
        monthly_living_expenses=0,
        monthly_debt_repayments=0,
        dependants=0,
        has_existing_loans=False,
        existing_loan_total=0,
        consent_to_share_profile=False,
        consent_to_share_documents=False,
        consent_to_credit_checks=False,
    )
    db.add(borrower)
    db.flush()
    return borrower


def _seed_company_borrower_account(
    db,
    company: LoanCompany,
    borrower: Borrower,
    label: str,
) -> CompanyBorrowerAccount:
    account = CompanyBorrowerAccount(
        company_id=company.id,
        borrower_id=borrower.id,
        account_reference=f"RLS-ACCOUNT-{label}-{uuid.uuid4().hex[:10]}",
        source="rls_probe",
        status="active",
        opening_fee_amount=0,
        opening_fee_currency="LSL",
        opening_fee_status="not_required",
    )
    db.add(account)
    db.flush()
    return account


def _seed_case(db, company: LoanCompany, borrower: Borrower, label: str) -> CRMRelationshipCase:
    case = CRMRelationshipCase(
        company_id=company.id,
        borrower_id=borrower.id,
        reference=f"RLS-{label}-{uuid.uuid4().hex[:10]}",
        relationship_stage="active",
        status="open",
        metadata_json={"probe": label},
    )
    db.add(case)
    db.flush()
    return case


def _set_probe_role_and_context(db, company_id: uuid.UUID) -> None:
    db.execute(text(f'SET LOCAL ROLE "{PROBE_ROLE}"'))
    db.execute(
        text("SELECT set_config('loanhub.user_id', :value, true)"),
        {"value": str(uuid.uuid4())},
    )
    db.execute(
        text("SELECT set_config('loanhub.company_id', :value, true)"),
        {"value": str(company_id)},
    )
    db.execute(text("SELECT set_config('loanhub.branch_id', '', true)"))
    db.execute(text("SELECT set_config('loanhub.role', 'company_admin', true)"))
    db.execute(text("SELECT set_config('loanhub.actor_scope', 'tenant', true)"))


def main() -> None:
    db = SessionLocal()
    company_a_id = company_b_id = borrower_a_id = borrower_b_id = case_a_id = case_b_id = None
    try:
        if db.bind is None or db.bind.dialect.name != "postgresql":
            raise RuntimeError("RLS verification requires PostgreSQL")

        company_a = _seed_company(db, "A")
        company_b = _seed_company(db, "B")
        borrower_a = _seed_borrower(db, "A")
        borrower_b = _seed_borrower(db, "B")
        _seed_company_borrower_account(db, company_a, borrower_a, "A")
        _seed_company_borrower_account(db, company_b, borrower_b, "B")
        case_a = _seed_case(db, company_a, borrower_a, "A")
        case_b = _seed_case(db, company_b, borrower_b, "B")
        company_a_id = company_a.id
        company_b_id = company_b.id
        borrower_a_id = borrower_a.id
        borrower_b_id = borrower_b.id
        case_a_id = case_a.id
        case_b_id = case_b.id
        db.commit()

        db.execute(text(f'DROP ROLE IF EXISTS "{PROBE_ROLE}"'))
        db.execute(
            text(
                f'CREATE ROLE "{PROBE_ROLE}" '
                "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            )
        )
        db.execute(text(f'GRANT USAGE ON SCHEMA public TO "{PROBE_ROLE}"'))
        db.execute(
            text(
                f'GRANT SELECT, INSERT, UPDATE, DELETE '
                f'ON TABLE crm_relationship_cases TO "{PROBE_ROLE}"'
            )
        )
        # The borrower-scope trigger reads these relationship tables before
        # PostgreSQL evaluates the CRM row-level INSERT policy.
        db.execute(
            text(
                f'GRANT SELECT ON TABLE company_borrower_accounts, client_company_loan '
                f'TO "{PROBE_ROLE}"'
            )
        )
        db.commit()

        _set_probe_role_and_context(db, company_a_id)

        visible = db.execute(
            text(
                """
                SELECT id, company_id
                FROM crm_relationship_cases
                WHERE id IN (:case_a, :case_b)
                ORDER BY id
                """
            ),
            {"case_a": case_a_id, "case_b": case_b_id},
        ).mappings().all()
        if len(visible) != 1 or visible[0]["company_id"] != company_a_id:
            raise AssertionError(
                f"RLS SELECT isolation failed: expected only Company A row, got {visible!r}"
            )

        updated = db.execute(
            text(
                """
                UPDATE crm_relationship_cases
                SET notes = 'cross-tenant-update-should-not-happen'
                WHERE id = :case_b
                """
            ),
            {"case_b": case_b_id},
        )
        if updated.rowcount != 0:
            raise AssertionError("RLS UPDATE isolation failed for Company B row")

        deleted = db.execute(
            text("DELETE FROM crm_relationship_cases WHERE id = :case_b"),
            {"case_b": case_b_id},
        )
        if deleted.rowcount != 0:
            raise AssertionError("RLS DELETE isolation failed for Company B row")

        cross_tenant_insert_blocked = False
        savepoint = db.begin_nested()
        try:
            db.execute(
                text(
                    """
                    INSERT INTO crm_relationship_cases (
                        id,
                        company_id,
                        borrower_id,
                        reference,
                        relationship_stage,
                        status,
                        metadata_json
                    )
                    VALUES (
                        :id,
                        :company_id,
                        :borrower_id,
                        :reference,
                        'active',
                        'open',
                        '{}'::jsonb
                    )
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "company_id": company_b_id,
                    "borrower_id": borrower_b_id,
                    "reference": f"RLS-X-{uuid.uuid4().hex[:10]}",
                },
            )
        except Exception as error:
            savepoint.rollback()
            if "row-level security" not in str(error).lower():
                raise
            cross_tenant_insert_blocked = True
        else:
            savepoint.rollback()

        if not cross_tenant_insert_blocked:
            raise AssertionError("RLS INSERT isolation failed for Company B row")

        db.rollback()
        print("LoanHub RLS pilot verification passed: cross-company SELECT/INSERT/UPDATE/DELETE are blocked.")
    finally:
        try:
            db.rollback()
            db.execute(text("RESET ROLE"))
            db.execute(text(f'DROP OWNED BY "{PROBE_ROLE}"'))
            db.execute(text(f'DROP ROLE IF EXISTS "{PROBE_ROLE}"'))
            db.commit()
        except Exception:
            db.rollback()

        if company_a_id and company_b_id:
            try:
                db.query(CRMRelationshipCase).filter(
                    CRMRelationshipCase.company_id.in_([company_a_id, company_b_id])
                ).delete(synchronize_session=False)
                if borrower_b_id:
                    # Users/borrowers are cleaned by transaction database disposal
                    # in CI; keep cleanup intentionally limited to pilot rows.
                    pass
                db.query(LoanCompany).filter(
                    LoanCompany.id.in_([company_a_id, company_b_id])
                ).delete(synchronize_session=False)
                db.commit()
            except Exception:
                db.rollback()
        db.close()


if __name__ == "__main__":
    main()
