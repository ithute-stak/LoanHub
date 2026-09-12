import enum


class RepaymentType(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    custom = "custom"

    DAILY = daily
    WEEKLY = weekly
    MONTHLY = monthly
    CUSTOM = custom


class LoanCalculationMethod(str, enum.Enum):
    """Supported interest and repayment calculation methods.

    The values are persisted as strings in products, offers and loans so new
    methods can be introduced without changing a PostgreSQL enum type.
    """

    MICRO_LOAN = "micro_loan"
    SIMPLE_INTEREST = "simple_interest"
    FLAT_RATE = "flat_rate"
    COMPOUND_INTEREST = "compound_interest"
    REDUCING_BALANCE = "reducing_balance"
    DAILY_ACCRUAL_REDUCING = "daily_accrual_reducing"


INTEREST_METHOD_LABELS: dict[LoanCalculationMethod, str] = {
    LoanCalculationMethod.MICRO_LOAN: "LoanHub Micro Loan Method",
    LoanCalculationMethod.SIMPLE_INTEREST: "Simple Interest",
    LoanCalculationMethod.FLAT_RATE: "Flat Rate",
    LoanCalculationMethod.COMPOUND_INTEREST: "Compound Interest",
    LoanCalculationMethod.REDUCING_BALANCE: "Reducing Balance (Amortised)",
    LoanCalculationMethod.DAILY_ACCRUAL_REDUCING: "Daily Accrual Reducing Balance (Actual/Month)",
}

class LoanStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    active = "active"
    completed = "completed"
    defaulted = "defaulted"
    rejected = "rejected"
    cancelled = "cancelled"

    PENDING = pending
    APPROVED = approved
    ACTIVE = active
    COMPLETED = completed
    DEFAULTED = defaulted
    REJECTED = rejected
    CANCELLED = cancelled


class RiskLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"

    LOW = low
    MEDIUM = medium
    HIGH = high


class UserRole(str, enum.Enum):
    # ``SUPERADMIN`` is retained as the original platform-owner role.
    SUPERADMIN = "superadmin"
    PLATFORM_ADMIN = "platform_admin"
    PLATFORM_FINANCE = "platform_finance"
    PLATFORM_SUPPORT = "platform_support"
    PLATFORM_AUDITOR = "platform_auditor"
    PLATFORM_OPERATIONS = "platform_operations"
    PLATFORM_COMPLIANCE = "platform_compliance"
    BORROWER = "borrower"

    COMPANY_OWNER = "company_owner"
    COMPANY_ADMIN = "company_admin"
    BRANCH_MANAGER = "branch_manager"
    LOAN_OFFICER = "loan_officer"
    FINANCE_OFFICER = "finance_officer"
    COLLECTIONS_OFFICER = "collections_officer"
    COMPLIANCE_OFFICER = "compliance_officer"
    AUDITOR = "auditor"
    CUSTOMER_SUPPORT = "customer_support"
    HR_MANAGER = "hr_manager"
    PERFORMANCE_MANAGER = "performance_manager"
    RISK_MANAGER = "risk_manager"
    IT_SUPPORT = "it_support"
    CREDIT_ANALYST = "credit_analyst"
    AML_CFT_OFFICER = "aml_cft_officer"
    TREASURY_OFFICER = "treasury_officer"
    DATA_PROTECTION_OFFICER = "data_protection_officer"
    REGULATORY_REPORTING_OFFICER = "regulatory_reporting_officer"
    OPERATIONS_OFFICER = "operations_officer"
    INFORMATION_SECURITY_OFFICER = "information_security_officer"


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class MaritalStatus(str, enum.Enum):
    SINGLE = "single"
    MARRIED = "married"
    DIVORCED = "divorced"
    WIDOWED = "widowed"


class EmploymentStatus(str, enum.Enum):
    EMPLOYED = "employed"
    SELF_EMPLOYED = "self_employed"
    UNEMPLOYED = "unemployed"
    STUDENT = "student"
    PENSIONER = "pensioner"


class CompanyStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class InstitutionType(str, enum.Enum):
    LOAN_COMPANY = "loan_company"
    COMMERCIAL_BANK = "commercial_bank"
    MICROFINANCE_INSTITUTION = "microfinance_institution"
    FINANCIAL_COOPERATIVE = "financial_cooperative"
    DEVELOPMENT_FINANCE_INSTITUTION = "development_finance_institution"
    GOVERNMENT_LENDING_PROGRAM = "government_lending_program"


class LoanRequestStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class DocumentType(str, enum.Enum):
    NATIONAL_ID = "national_id"
    PASSPORT = "passport"
    PAYSLIP = "payslip"
    BANK_STATEMENT = "bank_statement"
    PROOF_OF_RESIDENCE = "proof_of_residence"
    EMPLOYMENT_LETTER = "employment_letter"
    OTHER = "other"


class AccessRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class OfferStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING = "pending"
    SUSPENDED = "suspended"


class BillingCycle(str, enum.Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"
    PAY_PER_TRANSACTION = "pay_per_transaction"


class PaymentProvider(str, enum.Enum):
    CASH = "cash"
    LELEFAPAYGATE = "lelefapaygate"
    MPESA = "mpesa"
    ECOCASH = "ecocash"
    EFT = "eft"
    MANUAL = "manual"
    MOCK = "mock"


class PaymentMethod(str, enum.Enum):
    """LoanHub's posting boundary plus historical channel values.

    New electronic transactions use LELEFAPAYGATE. The legacy channel values
    remain readable for audit/history, but active handlers reject new postings
    through them so LoanHub never bypasses the gateway.
    """

    LELEFAPAYGATE = "lelefapaygate"
    BANK = "bank"
    SWIPPED = "swipped"
    GOLINK = "golink"
    CDAS = "cdas"
    MPESA_WALLET = "mpesa_wallet"
    MPESA_MERCHANT = "mpesa_merchant"
    MPESA_AGENT = "mpesa_agent"
    ECOCASH_WALLET = "ecocash_wallet"
    ECOCASH_AGENT = "ecocash_agent"
    ECOCASH_MERCHANT = "ecocash_merchant"
    CASH = "cash"


class TreasuryDirection(str, enum.Enum):
    MONEY_IN = "money_in"
    MONEY_OUT = "money_out"


class TreasuryEntryType(str, enum.Enum):
    OPENING_ADJUSTMENT = "opening_adjustment"
    OWNER_CONTRIBUTION = "owner_contribution"
    BRANCH_FUNDING = "branch_funding"
    LOAN_COLLECTION = "loan_collection"
    LOAN_DISBURSEMENT = "loan_disbursement"
    EXPENSE = "expense"
    BRANCH_REMITTANCE = "branch_remittance"
    PLATFORM_CHARGE = "platform_charge"
    REFUND = "refund"
    MANUAL_INCOME = "manual_income"
    ADJUSTMENT = "adjustment"
    OTHER = "other"


class OpeningSourceType(str, enum.Enum):
    PREVIOUS_CLOSING = "previous_closing"
    OWNER_CONTRIBUTION = "owner_contribution"
    HEADQUARTERS_FUNDING = "headquarters_funding"
    BANK_FLOAT = "bank_float"
    CASH_FLOAT = "cash_float"
    RETAINED_FUNDS = "retained_funds"
    OPENING_ADJUSTMENT = "opening_adjustment"
    OTHER = "other"


class TreasuryEntryApprovalStatus(str, enum.Enum):
    POSTED = "posted"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class TreasuryDayStatus(str, enum.Enum):
    OPEN = "open"
    SUBMITTED = "submitted"
    AUTO_SUBMITTED = "auto_submitted"
    REVIEWED = "reviewed"
    REOPENED = "reopened"


class BranchTransferStatus(str, enum.Enum):
    ISSUED = "issued"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REVERSED = "reversed"


class PaymentDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class PaymentPurpose(str, enum.Enum):
    SUBSCRIPTION = "subscription"
    MARKETPLACE_UNLOCK = "marketplace_unlock"
    LOAN_DISBURSEMENT = "loan_disbursement"
    LOAN_REPAYMENT = "loan_repayment"
    BORROW_REQUEST_FEE = "borrow_request_fee"
    ASSISTED_BORROWER_ACCOUNT_FEE = "assisted_borrower_account_fee"
    PLATFORM_FEE = "platform_fee"
    PLATFORM_TRANSACTION_CHARGE = "platform_transaction_charge"
    PLATFORM_CLAIM_SETTLEMENT = "platform_claim_settlement"
    DIRECT_DEBIT = "direct_debit"
    REFUND = "refund"
    BUSINESS_PAYMENT = "business_payment"


class UnlockStatus(str, enum.Enum):
    PENDING = "pending"
    UNLOCKED = "unlocked"
    FAILED = "failed"
    REVOKED = "revoked"


class InstallmentStatus(str, enum.Enum):
    PENDING = "pending"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    WAIVED = "waived"


class NotificationType(str, enum.Enum):
    LOAN_REQUEST = "loan_request"
    ACCESS_REQUEST = "access_request"
    OFFER = "offer"
    PAYMENT = "payment"
    SUBSCRIPTION = "subscription"
    SYSTEM = "system"
