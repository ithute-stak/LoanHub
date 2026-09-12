from __future__ import annotations

from datetime import date
from decimal import Decimal

from core.security import hash_password
from database.config.config import settings
from database.models.borrower import Borrower
from database.models.branch import CompanyBranch
from database.models.company import LoanCompany
from database.models.company_client import CompanyBorrowerAccount
from database.models.company_staff import CompanyStaff
from database.models.enums import (
    CompanyStatus,
    EmploymentStatus,
    Gender,
    InstitutionType,
    UserRole,
)
from database.models.person import Person
from database.models.user import User
from database.session import SessionLocal


SANDBOX_COMPANY_NAME = "LoanHub Sandbox Finance"
SANDBOX_COMPANY_REGISTRATION = "SANDBOX-ONLY-001"
# Keep seed fixtures as plain Python literals so isolation regression tests can
# inspect them safely without importing application/database runtime code.
SAMPLE_CLIENTS = (
    ("59010001", "Mpho", "Mokoena", "123456789012", "8500.00", "Ministry of Education"),
    ("59010002", "Lerato", "Molefe", "123456789013", "11250.00", "Maseru Retail Group"),
    ("59010003", "Thabo", "Mofokeng", "123456789014", "7200.00", "Maluti Construction"),
    ("59010004", "Palesa", "Ntaopane", "123456789015", "14600.00", "Lesotho Health Services"),
    ("59010005", "Kabelo", "Ramatheola", "123456789016", "9800.00", "Highlands Logistics"),
)

COMPANY_SANDBOX_ROLES = tuple(
    role
    for role in UserRole
    if role.value
    in {
        "company_owner",
        "company_admin",
        "branch_manager",
        "loan_officer",
        "finance_officer",
        "collections_officer",
        "compliance_officer",
        "auditor",
        "customer_support",
        "hr_manager",
        "performance_manager",
        "risk_manager",
        "it_support",
        "credit_analyst",
        "aml_cft_officer",
        "treasury_officer",
        "data_protection_officer",
        "regulatory_reporting_officer",
        "operations_officer",
        "information_security_officer",
    }
)


def require_sandbox() -> None:
    if not settings.SANDBOX_MODE:
        raise RuntimeError("Refusing to seed because SANDBOX_MODE is not enabled")
    if settings.DB_NAME.lower() in {"loanhub", "loan_db", "production", "prod"}:
        raise RuntimeError(
            f"Refusing to seed a production-looking database name: {settings.DB_NAME}"
        )


def get_or_create_demo_user(db) -> User:
    user = db.query(User).filter(User.phone == settings.SANDBOX_LOGIN_PHONE).first()
    if not user:
        user = User(
            phone=settings.SANDBOX_LOGIN_PHONE,
            email="sandbox@loanhub.co.ls",
            password_hash=hash_password(settings.SANDBOX_LOGIN_PASSWORD),
            role=UserRole.COMPANY_OWNER,
            is_active=True,
            is_verified=True,
            must_change_password=False,
        )
        db.add(user)
        db.flush()
    else:
        user.password_hash = hash_password(settings.SANDBOX_LOGIN_PASSWORD)
        user.role = UserRole.COMPANY_OWNER
        user.is_active = True
        user.is_verified = True
        user.must_change_password = False

    person = db.query(Person).filter(Person.user_id == user.id).first()
    if not person:
        db.add(
            Person(
                user_id=user.id,
                first_name="LoanHub",
                last_name="Sandbox Tester",
                gender=Gender.OTHER,
                date_of_birth=date(1990, 1, 1),
                nationality="Mosotho",
                district="Maseru",
                town_or_village="Maseru",
                physical_address="Synthetic sandbox profile - not a real person",
            )
        )

    borrower = db.query(Borrower).filter(Borrower.user_id == user.id).first()
    if not borrower:
        db.add(
            Borrower(
                user_id=user.id,
                employment_status=EmploymentStatus.EMPLOYED,
                employer_name="LoanHub Sandbox",
                job_title="Demo Borrower",
                monthly_income=Decimal("10000.00"),
                net_monthly_income=Decimal("9000.00"),
                other_monthly_income=Decimal("0.00"),
                monthly_living_expenses=Decimal("2500.00"),
                monthly_debt_repayments=Decimal("0.00"),
                dependants=0,
                has_existing_loans=False,
                existing_loan_total=Decimal("0.00"),
                consent_to_share_profile=True,
                consent_to_share_documents=True,
                consent_to_credit_checks=True,
            )
        )
    db.flush()
    return user


def get_or_create_company(db) -> tuple[LoanCompany, CompanyBranch]:
    company = (
        db.query(LoanCompany)
        .filter(LoanCompany.registration_number == SANDBOX_COMPANY_REGISTRATION)
        .first()
    )
    if not company:
        company = LoanCompany(
            name=SANDBOX_COMPANY_NAME,
            institution_type=InstitutionType.LOAN_COMPANY,
            registration_number=SANDBOX_COMPANY_REGISTRATION,
            license_number="SANDBOX-LICENSE-001",
            phone="+266 2231 0000",
            email="sandbox@loanhub.co.ls",
            website="https://sandbox.loanhub.co.ls",
            address="Synthetic training company - no real financial operations",
            district="Maseru",
            status=CompanyStatus.APPROVED,
            is_active=True,
        )
        db.add(company)
        db.flush()
    else:
        company.status = CompanyStatus.APPROVED
        company.is_active = True

    branch = (
        db.query(CompanyBranch)
        .filter(
            CompanyBranch.company_id == company.id,
            CompanyBranch.name == "Sandbox Head Office",
        )
        .first()
    )
    if not branch:
        branch = CompanyBranch(
            company_id=company.id,
            name="Sandbox Head Office",
            district="Maseru",
            town="Maseru",
            address="Synthetic sandbox branch",
            phone="+266 2231 0001",
            email="sandbox@loanhub.co.ls",
            is_active=True,
            is_headquarters=True,
        )
        db.add(branch)
        db.flush()
    return company, branch


def ensure_role_memberships(db, user: User, company: LoanCompany, branch: CompanyBranch) -> None:
    existing = {
        membership.role
        for membership in db.query(CompanyStaff)
        .filter(
            CompanyStaff.user_id == user.id,
            CompanyStaff.company_id == company.id,
        )
        .all()
    }
    for role in COMPANY_SANDBOX_ROLES:
        if role in existing:
            continue
        db.add(
            CompanyStaff(
                user_id=user.id,
                company_id=company.id,
                branch_id=branch.id,
                role=role,
                is_primary=role == UserRole.COMPANY_OWNER,
                is_active=True,
            )
        )


def ensure_sample_client(
    db,
    *,
    company: LoanCompany,
    branch: CompanyBranch,
    opened_by: User,
    phone: str,
    first_name: str,
    last_name: str,
    national_id: str,
    monthly_income: Decimal,
    employer_name: str,
    index: int,
) -> None:
    client_user = db.query(User).filter(User.phone == phone).first()
    if not client_user:
        client_user = User(
            phone=phone,
            email=f"sample{index}@sandbox.loanhub.co.ls",
            password_hash=hash_password(f"sandbox-client-{index}-disabled"),
            role=UserRole.BORROWER,
            is_active=True,
            is_verified=True,
            must_change_password=False,
        )
        db.add(client_user)
        db.flush()

    person = db.query(Person).filter(Person.user_id == client_user.id).first()
    if not person:
        db.add(
            Person(
                user_id=client_user.id,
                first_name=first_name,
                last_name=last_name,
                gender=Gender.FEMALE if index % 2 == 0 else Gender.MALE,
                date_of_birth=date(1985 + index, min(index + 1, 12), 10),
                national_id=national_id,
                nationality="Mosotho",
                district="Maseru",
                town_or_village="Maseru",
                physical_address="Synthetic sample client - sandbox only",
            )
        )

    borrower = db.query(Borrower).filter(Borrower.user_id == client_user.id).first()
    if not borrower:
        borrower = Borrower(
            user_id=client_user.id,
            employment_status=EmploymentStatus.EMPLOYED,
            employer_name=employer_name,
            job_title="Sample Employee",
            monthly_income=monthly_income,
            net_monthly_income=monthly_income * Decimal("0.88"),
            other_monthly_income=Decimal("0.00"),
            monthly_living_expenses=monthly_income * Decimal("0.30"),
            monthly_debt_repayments=Decimal("0.00"),
            dependants=index % 3,
            has_existing_loans=False,
            existing_loan_total=Decimal("0.00"),
            consent_to_share_profile=True,
            consent_to_share_documents=True,
            consent_to_credit_checks=True,
        )
        db.add(borrower)
        db.flush()

    account_reference = f"SBX-CLIENT-{index:03d}"
    account = (
        db.query(CompanyBorrowerAccount)
        .filter(CompanyBorrowerAccount.account_reference == account_reference)
        .first()
    )
    if not account:
        db.add(
            CompanyBorrowerAccount(
                company_id=company.id,
                branch_id=branch.id,
                borrower_id=borrower.id,
                opened_by_user_id=opened_by.id,
                account_reference=account_reference,
                source="sandbox_seed",
                status="active",
                opening_fee_amount=Decimal("0.00"),
                opening_fee_currency="LSL",
                opening_fee_status="not_required",
            )
        )


def seed() -> None:
    require_sandbox()
    db = SessionLocal()
    try:
        tester = get_or_create_demo_user(db)
        company, branch = get_or_create_company(db)
        ensure_role_memberships(db, tester, company, branch)
        for index, client in enumerate(SAMPLE_CLIENTS, start=1):
            ensure_sample_client(
                db,
                company=company,
                branch=branch,
                opened_by=tester,
                phone=client[0],
                first_name=client[1],
                last_name=client[2],
                national_id=client[3],
                monthly_income=Decimal(client[4]),
                employer_name=client[5],
                index=index,
            )
        db.commit()
        print(
            "Sandbox ready: public tester, all company roles, and 5 synthetic clients seeded."
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
