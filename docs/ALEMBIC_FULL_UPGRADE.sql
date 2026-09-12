BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 3057a2cdb0ea

CREATE TYPE userrole AS ENUM ('SUPERADMIN', 'BORROWER', 'COMPANY_ADMIN', 'BRANCH_MANAGER', 'LOAN_OFFICER');

CREATE TABLE users (
    email VARCHAR(150), 
    phone VARCHAR(30) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    role userrole NOT NULL, 
    is_active BOOLEAN, 
    is_verified BOOLEAN, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE UNIQUE INDEX ix_users_phone ON users (phone);

INSERT INTO alembic_version (version_num) VALUES ('3057a2cdb0ea') RETURNING alembic_version.version_num;

-- Running upgrade 3057a2cdb0ea -> 4ffb06dcde89

CREATE TYPE gender AS ENUM ('MALE', 'FEMALE', 'OTHER');

CREATE TYPE maritalstatus AS ENUM ('SINGLE', 'MARRIED', 'DIVORCED', 'WIDOWED');

CREATE TYPE employmentstatus AS ENUM ('EMPLOYED', 'SELF_EMPLOYED', 'UNEMPLOYED', 'STUDENT', 'PENSIONER');

CREATE TABLE borrowers (
    user_id UUID NOT NULL, 
    first_name VARCHAR(100) NOT NULL, 
    middle_name VARCHAR(100), 
    last_name VARCHAR(100) NOT NULL, 
    gender gender NOT NULL, 
    date_of_birth DATE NOT NULL, 
    national_id VARCHAR(50), 
    passport_number VARCHAR(50), 
    marital_status maritalstatus, 
    nationality VARCHAR(100), 
    district VARCHAR(100) NOT NULL, 
    town_or_village VARCHAR(150), 
    physical_address TEXT, 
    employment_status employmentstatus NOT NULL, 
    employer_name VARCHAR(200), 
    job_title VARCHAR(150), 
    monthly_income NUMERIC(12, 2), 
    salary_date VARCHAR(20), 
    has_existing_loans BOOLEAN, 
    existing_loan_total NUMERIC(12, 2), 
    consent_to_share_profile BOOLEAN, 
    consent_to_credit_checks BOOLEAN, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    UNIQUE (national_id), 
    UNIQUE (passport_number), 
    UNIQUE (user_id)
);

UPDATE alembic_version SET version_num='4ffb06dcde89' WHERE alembic_version.version_num = '3057a2cdb0ea';

-- Running upgrade 4ffb06dcde89 -> b0a8b024a79e

CREATE TYPE companystatus AS ENUM ('PENDING', 'APPROVED', 'REJECTED', 'SUSPENDED');

CREATE TABLE loan_companies (
    name VARCHAR(200) NOT NULL, 
    registration_number VARCHAR(100), 
    license_number VARCHAR(100), 
    phone VARCHAR(30) NOT NULL, 
    email VARCHAR(150), 
    website VARCHAR(200), 
    address TEXT, 
    district VARCHAR(100), 
    status companystatus, 
    is_active BOOLEAN, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    UNIQUE (license_number), 
    UNIQUE (name), 
    UNIQUE (registration_number)
);

UPDATE alembic_version SET version_num='b0a8b024a79e' WHERE alembic_version.version_num = '4ffb06dcde89';

-- Running upgrade b0a8b024a79e -> f86a6ab5a269

CREATE TABLE company_branches (
    company_id UUID NOT NULL, 
    name VARCHAR(150) NOT NULL, 
    district VARCHAR(100) NOT NULL, 
    town VARCHAR(100), 
    address TEXT, 
    phone VARCHAR(30), 
    email VARCHAR(150), 
    is_active BOOLEAN, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id)
);

UPDATE alembic_version SET version_num='f86a6ab5a269' WHERE alembic_version.version_num = 'b0a8b024a79e';

-- Running upgrade f86a6ab5a269 -> 96e6e94f2ba7

CREATE TABLE company_staff (
    user_id UUID NOT NULL, 
    company_id UUID NOT NULL, 
    branch_id UUID, 
    is_active BOOLEAN, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(branch_id) REFERENCES company_branches (id), 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

UPDATE alembic_version SET version_num='96e6e94f2ba7' WHERE alembic_version.version_num = 'f86a6ab5a269';

-- Running upgrade 96e6e94f2ba7 -> 790ed6fd651d

ALTER TABLE company_staff ADD COLUMN role userrole NOT NULL;

UPDATE alembic_version SET version_num='790ed6fd651d' WHERE alembic_version.version_num = '96e6e94f2ba7';

-- Running upgrade 790ed6fd651d -> 15c00a058229

CREATE TABLE loan_products (
    company_id UUID NOT NULL, 
    name VARCHAR(150) NOT NULL, 
    description TEXT, 
    min_amount NUMERIC(12, 2) NOT NULL, 
    max_amount NUMERIC(12, 2) NOT NULL, 
    min_term_months INTEGER NOT NULL, 
    max_term_months INTEGER NOT NULL, 
    interest_rate_percent NUMERIC(5, 2), 
    processing_fee NUMERIC(12, 2), 
    is_active BOOLEAN, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id)
);

UPDATE alembic_version SET version_num='15c00a058229' WHERE alembic_version.version_num = '790ed6fd651d';

-- Running upgrade 15c00a058229 -> d09fde6cd60e

CREATE TYPE loanrequeststatus AS ENUM ('DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'OFFERED', 'ACCEPTED', 'CANCELLED', 'EXPIRED');

CREATE TABLE loan_requests (
    borrower_id UUID NOT NULL, 
    requested_amount NUMERIC(12, 2) NOT NULL, 
    preferred_term_months INTEGER, 
    loan_purpose TEXT, 
    status loanrequeststatus, 
    visible_to_lenders BOOLEAN, 
    allow_lenders_to_call BOOLEAN, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(borrower_id) REFERENCES borrowers (id)
);

UPDATE alembic_version SET version_num='d09fde6cd60e' WHERE alembic_version.version_num = '15c00a058229';

-- Running upgrade d09fde6cd60e -> 8563cd58deb9

CREATE TYPE documenttype AS ENUM ('NATIONAL_ID', 'PASSPORT', 'PAYSLIP', 'BANK_STATEMENT', 'PROOF_OF_RESIDENCE', 'EMPLOYMENT_LETTER', 'OTHER');

CREATE TABLE borrower_documents (
    borrower_id UUID NOT NULL, 
    document_type documenttype NOT NULL, 
    file_name VARCHAR(255) NOT NULL, 
    file_url VARCHAR(500) NOT NULL, 
    is_verified BOOLEAN, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(borrower_id) REFERENCES borrowers (id)
);

CREATE TABLE loan_request_documents (
    loan_request_id UUID NOT NULL, 
    document_type documenttype NOT NULL, 
    file_name VARCHAR(255) NOT NULL, 
    file_url VARCHAR(500) NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(loan_request_id) REFERENCES loan_requests (id)
);

UPDATE alembic_version SET version_num='8563cd58deb9' WHERE alembic_version.version_num = 'd09fde6cd60e';

-- Running upgrade 8563cd58deb9 -> 464f4729f8a7

CREATE TYPE accessrequeststatus AS ENUM ('PENDING', 'APPROVED', 'REJECTED');

CREATE TABLE lender_access_requests (
    loan_request_id UUID NOT NULL, 
    company_id UUID NOT NULL, 
    requested_by_user_id UUID NOT NULL, 
    status accessrequeststatus, 
    message TEXT, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id), 
    FOREIGN KEY(loan_request_id) REFERENCES loan_requests (id), 
    FOREIGN KEY(requested_by_user_id) REFERENCES users (id)
);

UPDATE alembic_version SET version_num='464f4729f8a7' WHERE alembic_version.version_num = '8563cd58deb9';

-- Running upgrade 464f4729f8a7 -> 920a67b52323

CREATE TYPE offerstatus AS ENUM ('PENDING', 'ACCEPTED', 'REJECTED', 'WITHDRAWN');

CREATE TABLE loan_offers (
    loan_request_id UUID NOT NULL, 
    company_id UUID NOT NULL, 
    branch_id UUID, 
    offered_by_user_id UUID NOT NULL, 
    approved_amount NUMERIC(12, 2) NOT NULL, 
    term_months INTEGER NOT NULL, 
    interest_rate_percent NUMERIC(5, 2), 
    processing_fee NUMERIC(12, 2), 
    monthly_repayment NUMERIC(12, 2), 
    total_repayment NUMERIC(12, 2), 
    notes TEXT, 
    status offerstatus, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(branch_id) REFERENCES company_branches (id), 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id), 
    FOREIGN KEY(loan_request_id) REFERENCES loan_requests (id), 
    FOREIGN KEY(offered_by_user_id) REFERENCES users (id)
);

UPDATE alembic_version SET version_num='920a67b52323' WHERE alembic_version.version_num = '464f4729f8a7';

-- Running upgrade 920a67b52323 -> db8c1b7032c2

ALTER TABLE loan_requests ADD COLUMN selected_offer_id UUID;

ALTER TABLE loan_requests ADD CONSTRAINT loan_requests_selected_offer_id_fkey FOREIGN KEY(selected_offer_id) REFERENCES loan_offers (id);

UPDATE alembic_version SET version_num='db8c1b7032c2' WHERE alembic_version.version_num = '920a67b52323';

-- Running upgrade db8c1b7032c2 -> 77031f1f0be4

CREATE TYPE notificationtype AS ENUM ('LOAN_REQUEST', 'ACCESS_REQUEST', 'OFFER', 'SYSTEM');

CREATE TABLE notifications (
    user_id UUID NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    message TEXT NOT NULL, 
    notification_type notificationtype, 
    is_read BOOLEAN, 
    related_loan_request_id UUID, 
    related_offer_id UUID, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(related_loan_request_id) REFERENCES loan_requests (id), 
    FOREIGN KEY(related_offer_id) REFERENCES loan_offers (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

UPDATE alembic_version SET version_num='77031f1f0be4' WHERE alembic_version.version_num = 'db8c1b7032c2';

-- Running upgrade 77031f1f0be4 -> b0c4c142919a

CREATE TYPE subscriptionstatus AS ENUM ('ACTIVE', 'EXPIRED', 'CANCELLED', 'PENDING');

CREATE TABLE company_subscriptions (
    company_id UUID NOT NULL, 
    plan_name VARCHAR(100) NOT NULL, 
    amount NUMERIC(12, 2) NOT NULL, 
    start_date DATE NOT NULL, 
    end_date DATE NOT NULL, 
    status subscriptionstatus, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id)
);

UPDATE alembic_version SET version_num='b0c4c142919a' WHERE alembic_version.version_num = '77031f1f0be4';

-- Running upgrade b0c4c142919a -> 48e0a5d6cb1f

CREATE TABLE audit_logs (
    user_id UUID, 
    action VARCHAR(150) NOT NULL, 
    table_name VARCHAR(150), 
    record_id UUID, 
    description TEXT, 
    ip_address VARCHAR(100), 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

UPDATE alembic_version SET version_num='48e0a5d6cb1f' WHERE alembic_version.version_num = 'b0c4c142919a';

-- Running upgrade 48e0a5d6cb1f -> d16e137105d7

CREATE TABLE broadcast (
    user_id UUID, 
    channel VARCHAR(120) NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    message TEXT NOT NULL, 
    event_type VARCHAR(100) NOT NULL, 
    entity VARCHAR(100), 
    entity_id VARCHAR(100), 
    data JSONB, 
    is_read BOOLEAN, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

UPDATE alembic_version SET version_num='d16e137105d7' WHERE alembic_version.version_num = '48e0a5d6cb1f';

-- Running upgrade d16e137105d7 -> 44822a754848

CREATE TABLE refresh_tokens (
    jti VARCHAR(255) NOT NULL, 
    user_id UUID NOT NULL, 
    revoked BOOLEAN, 
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX ix_refresh_tokens_jti ON refresh_tokens (jti);

UPDATE alembic_version SET version_num='44822a754848' WHERE alembic_version.version_num = 'd16e137105d7';

-- Running upgrade 44822a754848 -> 80d0284b8cd6

CREATE TYPE repaymenttype AS ENUM ('daily', 'weekly', 'monthly', 'custom');

CREATE TYPE loanstatus AS ENUM ('pending', 'approved', 'active', 'completed', 'defaulted', 'rejected');

CREATE TYPE risklevel AS ENUM ('low', 'medium', 'high');

CREATE TABLE client_company_loan (
    company_id UUID, 
    borrower_id UUID NOT NULL, 
    loan_reference VARCHAR(50), 
    principal_amount NUMERIC(15, 2) NOT NULL, 
    interest_rate NUMERIC(5, 2) NOT NULL, 
    total_repayable NUMERIC(15, 2) NOT NULL, 
    repayment_type repaymenttype NOT NULL, 
    repayment_period INTEGER NOT NULL, 
    installment_amount NUMERIC(15, 2) NOT NULL, 
    disbursed_at TIMESTAMP WITHOUT TIME ZONE, 
    first_payment_due DATE, 
    maturity_date DATE, 
    amount_paid NUMERIC(15, 2), 
    balance NUMERIC(15, 2) NOT NULL, 
    status loanstatus, 
    risk_level risklevel, 
    is_overdue BOOLEAN, 
    created_by BIGINT, 
    approved_by BIGINT, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(borrower_id) REFERENCES borrowers (id), 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id)
);

CREATE UNIQUE INDEX ix_client_company_loan_loan_reference ON client_company_loan (loan_reference);

UPDATE alembic_version SET version_num='80d0284b8cd6' WHERE alembic_version.version_num = '44822a754848';

-- Running upgrade 80d0284b8cd6 -> a56c9061c634

ALTER TABLE client_company_loan ADD COLUMN loan_request_id UUID NOT NULL;

ALTER TABLE client_company_loan ADD COLUMN loan_offer_id UUID NOT NULL;

ALTER TABLE client_company_loan ALTER COLUMN company_id SET NOT NULL;

ALTER TABLE client_company_loan ALTER COLUMN created_at DROP NOT NULL;

ALTER TABLE client_company_loan ADD CONSTRAINT client_company_loan_loan_request_id_fkey FOREIGN KEY(loan_request_id) REFERENCES loan_requests (id);

ALTER TABLE client_company_loan ADD CONSTRAINT client_company_loan_loan_offer_id_fkey FOREIGN KEY(loan_offer_id) REFERENCES loan_offers (id);

ALTER TABLE loan_offers ALTER COLUMN created_at DROP NOT NULL;

ALTER TABLE loan_requests ALTER COLUMN created_at DROP NOT NULL;

ALTER TABLE loan_requests DROP CONSTRAINT loan_requests_selected_offer_id_fkey;

UPDATE alembic_version SET version_num='a56c9061c634' WHERE alembic_version.version_num = '80d0284b8cd6';

-- Running upgrade a56c9061c634 -> cdb7c1666d74

DROP INDEX ix_client_company_loan_loan_reference;

DROP TABLE client_company_loan;

UPDATE alembic_version SET version_num='cdb7c1666d74' WHERE alembic_version.version_num = 'a56c9061c634';

-- Running upgrade cdb7c1666d74 -> 056d9353ae4b

CREATE TABLE client_company_loan (
    loan_request_id UUID NOT NULL, 
    loan_offer_id UUID NOT NULL, 
    company_id UUID NOT NULL, 
    borrower_id UUID NOT NULL, 
    loan_reference VARCHAR(50), 
    principal_amount NUMERIC(15, 2) NOT NULL, 
    interest_rate NUMERIC(5, 2) NOT NULL, 
    total_repayable NUMERIC(15, 2) NOT NULL, 
    repayment_period INTEGER NOT NULL, 
    installment_amount NUMERIC(15, 2) NOT NULL, 
    disbursed_at TIMESTAMP WITHOUT TIME ZONE, 
    first_payment_due DATE, 
    maturity_date DATE, 
    amount_paid NUMERIC(15, 2), 
    balance NUMERIC(15, 2) NOT NULL, 
    risk_level risklevel, 
    is_overdue BOOLEAN, 
    created_by UUID, 
    approved_by UUID, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
    id UUID NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(approved_by) REFERENCES users (id), 
    FOREIGN KEY(borrower_id) REFERENCES borrowers (id), 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id), 
    FOREIGN KEY(created_by) REFERENCES users (id), 
    FOREIGN KEY(loan_offer_id) REFERENCES loan_offers (id), 
    FOREIGN KEY(loan_request_id) REFERENCES loan_requests (id)
);

CREATE UNIQUE INDEX ix_client_company_loan_loan_reference ON client_company_loan (loan_reference);

UPDATE alembic_version SET version_num='056d9353ae4b' WHERE alembic_version.version_num = 'cdb7c1666d74';

-- Running upgrade 056d9353ae4b -> af6a1575fb01

ALTER TABLE client_company_loan ADD COLUMN repayment_type repaymenttype NOT NULL;

ALTER TABLE client_company_loan ADD COLUMN status loanstatus;

ALTER TABLE client_company_loan ADD COLUMN risk_level risklevel;

UPDATE alembic_version SET version_num='af6a1575fb01' WHERE alembic_version.version_num = '056d9353ae4b';

-- Running upgrade af6a1575fb01 -> fd4aa8a11b41

UPDATE alembic_version SET version_num='fd4aa8a11b41' WHERE alembic_version.version_num = 'af6a1575fb01';

-- Running upgrade fd4aa8a11b41 -> 7ba90e8af6b6

CREATE TABLE people (
    user_id UUID NOT NULL, 
    first_name VARCHAR(100) NOT NULL, 
    middle_name VARCHAR(100), 
    last_name VARCHAR(100) NOT NULL, 
    gender gender, 
    date_of_birth DATE, 
    national_id VARCHAR(50), 
    passport_number VARCHAR(50), 
    marital_status maritalstatus, 
    nationality VARCHAR(100), 
    district VARCHAR(100), 
    town_or_village VARCHAR(150), 
    physical_address TEXT, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    CONSTRAINT pk_people PRIMARY KEY (id), 
    CONSTRAINT fk_people_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX ix_people_user_id ON people (user_id);

CREATE UNIQUE INDEX ix_people_national_id ON people (national_id);

CREATE UNIQUE INDEX ix_people_passport_number ON people (passport_number);

INSERT INTO people (
                id,
                user_id,
                first_name,
                middle_name,
                last_name,
                gender,
                date_of_birth,
                national_id,
                passport_number,
                marital_status,
                nationality,
                district,
                town_or_village,
                physical_address,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            SELECT
                id,
                user_id,
                first_name,
                middle_name,
                last_name,
                gender,
                date_of_birth,
                national_id,
                passport_number,
                marital_status,
                nationality,
                district,
                town_or_village,
                physical_address,
                COALESCE(created_at, NOW()),
                COALESCE(updated_at, NOW()),
                created_by,
                updated_by
            FROM borrowers;

DO $$
            DECLARE
                missing_count BIGINT;
            BEGIN
                SELECT COUNT(*)
                  INTO missing_count
                  FROM borrowers AS borrower
                  LEFT JOIN people AS person
                    ON person.user_id = borrower.user_id
                 WHERE person.id IS NULL;

                IF missing_count > 0 THEN
                    RAISE EXCEPTION
                        '% borrower records were not copied into people',
                        missing_count;
                END IF;
            END
            $$;;

UPDATE borrowers
            SET has_existing_loans = FALSE
            WHERE has_existing_loans IS NULL;

UPDATE borrowers
            SET existing_loan_total = 0
            WHERE existing_loan_total IS NULL;

UPDATE borrowers
            SET consent_to_share_profile = FALSE
            WHERE consent_to_share_profile IS NULL;

UPDATE borrowers
            SET consent_to_credit_checks = FALSE
            WHERE consent_to_credit_checks IS NULL;

UPDATE refresh_tokens
            SET revoked = FALSE
            WHERE revoked IS NULL;

UPDATE users
            SET is_active = TRUE
            WHERE is_active IS NULL;

UPDATE users
            SET is_verified = FALSE
            WHERE is_verified IS NULL;

ALTER TABLE borrowers ALTER COLUMN has_existing_loans SET NOT NULL;

ALTER TABLE borrowers ALTER COLUMN existing_loan_total SET NOT NULL;

ALTER TABLE borrowers ALTER COLUMN consent_to_share_profile SET NOT NULL;

ALTER TABLE borrowers ALTER COLUMN consent_to_credit_checks SET NOT NULL;

ALTER TABLE refresh_tokens ALTER COLUMN revoked SET NOT NULL;

ALTER TABLE users ALTER COLUMN is_active SET NOT NULL;

ALTER TABLE users ALTER COLUMN is_verified SET NOT NULL;

ALTER TABLE borrowers DROP CONSTRAINT borrowers_national_id_key;

ALTER TABLE borrowers DROP CONSTRAINT borrowers_passport_number_key;

ALTER TABLE borrowers DROP CONSTRAINT borrowers_user_id_key;

CREATE UNIQUE INDEX ix_borrowers_user_id ON borrowers (user_id);

ALTER TABLE borrowers DROP CONSTRAINT borrowers_user_id_fkey;

ALTER TABLE borrowers ADD CONSTRAINT fk_borrowers_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE;

ALTER TABLE borrowers DROP COLUMN nationality;

ALTER TABLE borrowers DROP COLUMN date_of_birth;

ALTER TABLE borrowers DROP COLUMN gender;

ALTER TABLE borrowers DROP COLUMN passport_number;

ALTER TABLE borrowers DROP COLUMN physical_address;

ALTER TABLE borrowers DROP COLUMN national_id;

ALTER TABLE borrowers DROP COLUMN district;

ALTER TABLE borrowers DROP COLUMN town_or_village;

ALTER TABLE borrowers DROP COLUMN first_name;

ALTER TABLE borrowers DROP COLUMN last_name;

ALTER TABLE borrowers DROP COLUMN middle_name;

ALTER TABLE borrowers DROP COLUMN marital_status;

UPDATE alembic_version SET version_num='7ba90e8af6b6' WHERE alembic_version.version_num = 'fd4aa8a11b41';

-- Running upgrade 7ba90e8af6b6 -> 9f1c2d3e4a5b

ALTER TYPE "userrole" ADD VALUE IF NOT EXISTS 'COMPANY_OWNER';

ALTER TYPE "userrole" ADD VALUE IF NOT EXISTS 'FINANCE_OFFICER';

ALTER TYPE "userrole" ADD VALUE IF NOT EXISTS 'COLLECTIONS_OFFICER';

ALTER TYPE "userrole" ADD VALUE IF NOT EXISTS 'COMPLIANCE_OFFICER';

ALTER TYPE "userrole" ADD VALUE IF NOT EXISTS 'AUDITOR';

ALTER TYPE "userrole" ADD VALUE IF NOT EXISTS 'CUSTOMER_SUPPORT';

ALTER TYPE "loanrequeststatus" ADD VALUE IF NOT EXISTS 'OPEN';

ALTER TYPE "offerstatus" ADD VALUE IF NOT EXISTS 'EXPIRED';

ALTER TYPE "subscriptionstatus" ADD VALUE IF NOT EXISTS 'SUSPENDED';

ALTER TYPE "loanstatus" ADD VALUE IF NOT EXISTS 'cancelled';

CREATE TYPE billingcycle AS ENUM ('MONTHLY', 'ANNUAL', 'PAY_PER_TRANSACTION');

CREATE TYPE paymentprovider AS ENUM ('MPESA', 'ECOCASH', 'MANUAL', 'MOCK');

CREATE TYPE paymentstatus AS ENUM ('PENDING', 'PROCESSING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'REVERSED');

CREATE TYPE paymentdirection AS ENUM ('INBOUND', 'OUTBOUND');

CREATE TYPE paymentpurpose AS ENUM ('SUBSCRIPTION', 'MARKETPLACE_UNLOCK', 'LOAN_DISBURSEMENT', 'LOAN_REPAYMENT', 'PLATFORM_FEE', 'REFUND');

CREATE TYPE unlockstatus AS ENUM ('PENDING', 'UNLOCKED', 'FAILED', 'REVOKED');

CREATE TYPE installmentstatus AS ENUM ('PENDING', 'PARTIALLY_PAID', 'PAID', 'OVERDUE', 'WAIVED');

UPDATE loan_companies SET status = 'PENDING' WHERE status IS NULL;

UPDATE loan_companies SET is_active = FALSE WHERE is_active IS NULL;

UPDATE company_branches SET is_active = TRUE WHERE is_active IS NULL;

UPDATE company_staff SET is_active = TRUE WHERE is_active IS NULL;

ALTER TABLE loan_companies ALTER COLUMN status SET NOT NULL;

ALTER TABLE loan_companies ALTER COLUMN is_active SET NOT NULL;

ALTER TABLE company_branches ALTER COLUMN is_active SET NOT NULL;

ALTER TABLE company_staff ALTER COLUMN is_active SET NOT NULL;

ALTER TABLE company_branches ADD CONSTRAINT uq_company_branch_name UNIQUE (company_id, name);

ALTER TABLE company_staff ADD CONSTRAINT uq_company_staff_user_company UNIQUE (user_id, company_id);

CREATE INDEX ix_company_branches_company_id ON company_branches (company_id);

CREATE INDEX ix_company_staff_company_id ON company_staff (company_id);

CREATE INDEX ix_company_staff_branch_id ON company_staff (branch_id);

CREATE INDEX ix_company_staff_user_id ON company_staff (user_id);

UPDATE loan_products SET processing_fee = 0 WHERE processing_fee IS NULL;

UPDATE loan_products SET interest_rate_percent = 0 WHERE interest_rate_percent IS NULL;

UPDATE loan_products SET is_active = TRUE WHERE is_active IS NULL;

ALTER TABLE loan_products ALTER COLUMN interest_rate_percent TYPE NUMERIC(6, 3);

ALTER TABLE loan_products ALTER COLUMN interest_rate_percent SET NOT NULL;

ALTER TABLE loan_products ALTER COLUMN processing_fee SET NOT NULL;

ALTER TABLE loan_products ALTER COLUMN is_active SET NOT NULL;

CREATE INDEX ix_loan_products_company_id ON loan_products (company_id);

UPDATE loan_requests SET status = 'SUBMITTED' WHERE status IS NULL;

UPDATE loan_requests SET visible_to_lenders = FALSE WHERE visible_to_lenders IS NULL;

UPDATE loan_requests SET allow_lenders_to_call = TRUE WHERE allow_lenders_to_call IS NULL;

ALTER TABLE loan_requests ALTER COLUMN status SET NOT NULL;

ALTER TABLE loan_requests ALTER COLUMN visible_to_lenders SET NOT NULL;

ALTER TABLE loan_requests ALTER COLUMN allow_lenders_to_call SET NOT NULL;

ALTER TABLE loan_requests ADD COLUMN submitted_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE loan_requests ADD COLUMN expires_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE loan_requests ADD COLUMN accepted_at TIMESTAMP WITHOUT TIME ZONE;

CREATE INDEX ix_loan_requests_status ON loan_requests (status);

CREATE INDEX ix_loan_requests_expires_at ON loan_requests (expires_at);

CREATE INDEX ix_loan_requests_borrower_id ON loan_requests (borrower_id);

ALTER TABLE loan_requests ADD CONSTRAINT uq_loan_requests_selected_offer UNIQUE (selected_offer_id);

UPDATE loan_offers
            SET interest_rate_percent = COALESCE(interest_rate_percent, 0),
                processing_fee = COALESCE(processing_fee, 0),
                total_repayment = COALESCE(
                    total_repayment,
                    approved_amount
                    + (approved_amount * COALESCE(interest_rate_percent, 0) / 100 * term_months / 12)
                    + COALESCE(processing_fee, 0)
                );

UPDATE loan_offers
            SET monthly_repayment = COALESCE(monthly_repayment, total_repayment / NULLIF(term_months, 0)),
                status = COALESCE(status, 'PENDING');

ALTER TABLE loan_offers ALTER COLUMN interest_rate_percent TYPE NUMERIC(6, 3);

ALTER TABLE loan_offers ALTER COLUMN interest_rate_percent SET NOT NULL;

ALTER TABLE loan_offers ALTER COLUMN processing_fee SET NOT NULL;

ALTER TABLE loan_offers ALTER COLUMN monthly_repayment SET NOT NULL;

ALTER TABLE loan_offers ALTER COLUMN total_repayment SET NOT NULL;

ALTER TABLE loan_offers ALTER COLUMN status SET NOT NULL;

ALTER TABLE loan_offers ADD COLUMN expires_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE loan_offers ADD COLUMN accepted_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE loan_offers ADD CONSTRAINT uq_loan_offer_request_company UNIQUE (loan_request_id, company_id);

CREATE INDEX ix_loan_offers_request_id ON loan_offers (loan_request_id);

CREATE INDEX ix_loan_offers_company_id ON loan_offers (company_id);

CREATE INDEX ix_loan_offers_branch_id ON loan_offers (branch_id);

CREATE INDEX ix_loan_offers_status ON loan_offers (status);

CREATE TABLE subscription_plans (
    code VARCHAR(60) NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    description VARCHAR(500), 
    monthly_price NUMERIC(12, 2) NOT NULL, 
    annual_price NUMERIC(12, 2) NOT NULL, 
    marketplace_unlock_fee NUMERIC(12, 2) NOT NULL, 
    transaction_fee_percent NUMERIC(6, 3) NOT NULL, 
    features JSONB NOT NULL, 
    limits JSONB NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    is_public BOOLEAN NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    UNIQUE (code)
);

CREATE UNIQUE INDEX ix_subscription_plans_code ON subscription_plans (code);

INSERT INTO subscription_plans (
                id,
                code,
                name,
                description,
                monthly_price,
                annual_price,
                marketplace_unlock_fee,
                transaction_fee_percent,
                features,
                limits,
                is_active,
                is_public
            )
            VALUES
                (
                    '00000000-0000-4000-8000-000000000001'::uuid,
                    'STARTER',
                    'Starter',
                    'Pay per marketplace unlock for smaller lenders.',
                    0,
                    0,
                    25,
                    1.5,
                    '{"marketplace_full_access": false}'::jsonb,
                    '{"branches": 1, "staff": 5, "products": 3}'::jsonb,
                    TRUE,
                    TRUE
                ),
                (
                    '00000000-0000-4000-8000-000000000002'::uuid,
                    'GROWTH',
                    'Growth',
                    'Monthly access for growing multi-branch lenders.',
                    799,
                    7990,
                    0,
                    1.0,
                    '{"marketplace_full_access": true}'::jsonb,
                    '{"branches": 10, "staff": 50, "products": 25}'::jsonb,
                    TRUE,
                    TRUE
                ),
                (
                    '00000000-0000-4000-8000-000000000003'::uuid,
                    'ENTERPRISE',
                    'Enterprise',
                    'Unlimited company operations and advanced controls.',
                    1999,
                    19990,
                    0,
                    0.5,
                    '{
                        "marketplace_full_access": true,
                        "priority_support": true
                    }'::jsonb,
                    '{"branches": -1, "staff": -1, "products": -1}'::jsonb,
                    TRUE,
                    TRUE
                )
            ON CONFLICT (code) DO NOTHING;

ALTER TABLE company_subscriptions ADD COLUMN plan_id UUID;

ALTER TABLE company_subscriptions ADD COLUMN billing_cycle billingcycle;

ALTER TABLE company_subscriptions ADD COLUMN auto_renew BOOLEAN DEFAULT false NOT NULL;

ALTER TABLE company_subscriptions ADD COLUMN payment_provider paymentprovider;

ALTER TABLE company_subscriptions ADD COLUMN external_reference VARCHAR(160);

UPDATE company_subscriptions SET status = 'PENDING' WHERE status IS NULL;

UPDATE company_subscriptions SET billing_cycle = 'MONTHLY' WHERE billing_cycle IS NULL;

ALTER TABLE company_subscriptions ALTER COLUMN status SET NOT NULL;

ALTER TABLE company_subscriptions ALTER COLUMN billing_cycle SET NOT NULL;

ALTER TABLE company_subscriptions ADD CONSTRAINT fk_company_subscription_plan FOREIGN KEY(plan_id) REFERENCES subscription_plans (id) ON DELETE RESTRICT;

CREATE INDEX ix_company_subscriptions_company_id ON company_subscriptions (company_id);

CREATE INDEX ix_company_subscriptions_plan_id ON company_subscriptions (plan_id);

ALTER TABLE company_subscriptions ADD CONSTRAINT uq_company_subscription_external_reference UNIQUE (external_reference);

ALTER TABLE client_company_loan DROP CONSTRAINT IF EXISTS client_company_loan_created_by_fkey;

ALTER TABLE client_company_loan DROP CONSTRAINT IF EXISTS client_company_loan_approved_by_fkey;

ALTER TABLE client_company_loan ALTER COLUMN created_by TYPE VARCHAR(36) USING created_by::text;

ALTER TABLE client_company_loan DROP COLUMN approved_by;

ALTER TABLE client_company_loan ADD COLUMN branch_id UUID;

ALTER TABLE client_company_loan ADD COLUMN processing_fee NUMERIC(15, 2) DEFAULT '0' NOT NULL;

ALTER TABLE client_company_loan ADD COLUMN approved_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE client_company_loan ADD COLUMN approved_by_user_id UUID;

ALTER TABLE client_company_loan ADD COLUMN disbursed_by_user_id UUID;

UPDATE client_company_loan SET loan_reference = 'LH-MIGRATED-' || UPPER(SUBSTRING(id::text, 1, 8)) WHERE loan_reference IS NULL;

UPDATE client_company_loan SET amount_paid = 0 WHERE amount_paid IS NULL;

UPDATE client_company_loan SET status = 'pending' WHERE status IS NULL;

UPDATE client_company_loan SET risk_level = 'low' WHERE risk_level IS NULL;

UPDATE client_company_loan SET is_overdue = FALSE WHERE is_overdue IS NULL;

UPDATE client_company_loan SET created_at = NOW() WHERE created_at IS NULL;

ALTER TABLE client_company_loan ALTER COLUMN loan_reference SET NOT NULL;

ALTER TABLE client_company_loan ALTER COLUMN interest_rate TYPE NUMERIC(6, 3);

ALTER TABLE client_company_loan ALTER COLUMN interest_rate SET NOT NULL;

ALTER TABLE client_company_loan ALTER COLUMN amount_paid SET NOT NULL;

ALTER TABLE client_company_loan ALTER COLUMN status SET NOT NULL;

ALTER TABLE client_company_loan ALTER COLUMN risk_level SET NOT NULL;

ALTER TABLE client_company_loan ALTER COLUMN is_overdue SET NOT NULL;

ALTER TABLE client_company_loan ALTER COLUMN created_at SET NOT NULL;

ALTER TABLE client_company_loan ADD CONSTRAINT fk_client_loan_branch FOREIGN KEY(branch_id) REFERENCES company_branches (id) ON DELETE SET NULL;

ALTER TABLE client_company_loan ADD CONSTRAINT fk_client_loan_approved_by FOREIGN KEY(approved_by_user_id) REFERENCES users (id) ON DELETE SET NULL;

ALTER TABLE client_company_loan ADD CONSTRAINT fk_client_loan_disbursed_by FOREIGN KEY(disbursed_by_user_id) REFERENCES users (id) ON DELETE SET NULL;

ALTER TABLE client_company_loan ADD CONSTRAINT uq_client_loan_request UNIQUE (loan_request_id);

ALTER TABLE client_company_loan ADD CONSTRAINT uq_client_loan_offer UNIQUE (loan_offer_id);

CREATE INDEX ix_client_loan_company_id ON client_company_loan (company_id);

CREATE INDEX ix_client_loan_branch_id ON client_company_loan (branch_id);

CREATE INDEX ix_client_loan_borrower_id ON client_company_loan (borrower_id);

CREATE TABLE payment_transactions (
    company_id UUID, 
    borrower_id UUID, 
    loan_request_id UUID, 
    loan_id UUID, 
    initiated_by_user_id UUID, 
    provider paymentprovider NOT NULL, 
    direction paymentdirection NOT NULL, 
    purpose paymentpurpose NOT NULL, 
    status paymentstatus NOT NULL, 
    amount NUMERIC(15, 2) NOT NULL, 
    currency VARCHAR(3) NOT NULL, 
    payer_phone VARCHAR(30), 
    payee_phone VARCHAR(30), 
    idempotency_key VARCHAR(120) NOT NULL, 
    provider_reference VARCHAR(180), 
    provider_payload JSONB NOT NULL, 
    failure_reason TEXT, 
    completed_at TIMESTAMP WITHOUT TIME ZONE, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id) ON DELETE SET NULL, 
    FOREIGN KEY(borrower_id) REFERENCES borrowers (id) ON DELETE SET NULL, 
    FOREIGN KEY(loan_request_id) REFERENCES loan_requests (id) ON DELETE SET NULL, 
    FOREIGN KEY(loan_id) REFERENCES client_company_loan (id) ON DELETE SET NULL, 
    FOREIGN KEY(initiated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
    UNIQUE (idempotency_key), 
    UNIQUE (provider_reference)
);

CREATE INDEX ix_payment_company_id ON payment_transactions (company_id);

CREATE INDEX ix_payment_borrower_id ON payment_transactions (borrower_id);

CREATE INDEX ix_payment_loan_request_id ON payment_transactions (loan_request_id);

CREATE INDEX ix_payment_loan_id ON payment_transactions (loan_id);

CREATE UNIQUE INDEX ix_payment_idempotency ON payment_transactions (idempotency_key);

CREATE UNIQUE INDEX ix_payment_provider_reference ON payment_transactions (provider_reference);

CREATE TABLE marketplace_unlocks (
    company_id UUID NOT NULL, 
    loan_request_id UUID NOT NULL, 
    payment_transaction_id UUID, 
    unlocked_by_user_id UUID, 
    price_paid NUMERIC(12, 2) NOT NULL, 
    status unlockstatus NOT NULL, 
    unlocked_at TIMESTAMP WITHOUT TIME ZONE, 
    expires_at TIMESTAMP WITHOUT TIME ZONE, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id) ON DELETE CASCADE, 
    FOREIGN KEY(loan_request_id) REFERENCES loan_requests (id) ON DELETE CASCADE, 
    FOREIGN KEY(payment_transaction_id) REFERENCES payment_transactions (id) ON DELETE SET NULL, 
    FOREIGN KEY(unlocked_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT uq_marketplace_unlock_company_request UNIQUE (company_id, loan_request_id), 
    UNIQUE (payment_transaction_id)
);

CREATE INDEX ix_marketplace_unlock_company ON marketplace_unlocks (company_id);

CREATE INDEX ix_marketplace_unlock_request ON marketplace_unlocks (loan_request_id);

CREATE TABLE repayment_installments (
    loan_id UUID NOT NULL, 
    installment_number INTEGER NOT NULL, 
    due_date DATE NOT NULL, 
    principal_due NUMERIC(15, 2) NOT NULL, 
    interest_due NUMERIC(15, 2) NOT NULL, 
    fee_due NUMERIC(15, 2) NOT NULL, 
    total_due NUMERIC(15, 2) NOT NULL, 
    paid_amount NUMERIC(15, 2) NOT NULL, 
    status installmentstatus NOT NULL, 
    paid_at TIMESTAMP WITHOUT TIME ZONE, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(loan_id) REFERENCES client_company_loan (id) ON DELETE CASCADE, 
    CONSTRAINT uq_repayment_installment_loan_number UNIQUE (loan_id, installment_number)
);

CREATE INDEX ix_repayment_installment_loan ON repayment_installments (loan_id);

CREATE INDEX ix_repayment_installment_due ON repayment_installments (due_date);

CREATE TABLE payment_allocations (
    payment_id UUID NOT NULL, 
    installment_id UUID NOT NULL, 
    amount NUMERIC(15, 2) NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(payment_id) REFERENCES payment_transactions (id) ON DELETE CASCADE, 
    FOREIGN KEY(installment_id) REFERENCES repayment_installments (id) ON DELETE CASCADE, 
    CONSTRAINT uq_payment_allocation_payment_installment UNIQUE (payment_id, installment_id)
);

CREATE INDEX ix_payment_allocation_payment ON payment_allocations (payment_id);

CREATE INDEX ix_payment_allocation_installment ON payment_allocations (installment_id);

UPDATE alembic_version SET version_num='9f1c2d3e4a5b' WHERE alembic_version.version_num = '7ba90e8af6b6';

-- Running upgrade 9f1c2d3e4a5b -> 307dcdf0187c

DO $$
        DECLARE
            item RECORD;
        BEGIN
            FOR item IN
                SELECT constraint_row.conname
                  FROM pg_constraint AS constraint_row
                  JOIN pg_class AS source_table
                    ON source_table.oid = constraint_row.conrelid
                  JOIN pg_namespace AS source_schema
                    ON source_schema.oid = source_table.relnamespace
                 WHERE constraint_row.contype = 'f'
                   AND source_schema.nspname = current_schema()
                   AND source_table.relname = 'company_staff'
                   AND constraint_row.confrelid =
                       'loan_companies'::regclass
                   AND EXISTS (
                        SELECT 1
                          FROM unnest(constraint_row.conkey)
                               AS key_column(attnum)
                          JOIN pg_attribute AS attribute_row
                            ON attribute_row.attrelid =
                               constraint_row.conrelid
                           AND attribute_row.attnum =
                               key_column.attnum
                         WHERE attribute_row.attname = 'company_id'
                   )
            LOOP
                EXECUTE format(
                    'ALTER TABLE company_staff DROP CONSTRAINT %I',
                    item.conname
                );
            END LOOP;

            ALTER TABLE company_staff
            ADD CONSTRAINT company_staff_company_id_fkey
            FOREIGN KEY (company_id)
            REFERENCES loan_companies (id) ON DELETE CASCADE;
        END
        $$;;

UPDATE alembic_version SET version_num='307dcdf0187c' WHERE alembic_version.version_num = '9f1c2d3e4a5b';

-- Running upgrade 307dcdf0187c -> 46b05ea64319

ALTER TABLE payment_transactions ALTER COLUMN idempotency_key TYPE VARCHAR(255);

UPDATE alembic_version SET version_num='46b05ea64319' WHERE alembic_version.version_num = '307dcdf0187c';

-- Running upgrade 46b05ea64319 -> 274950a4cd45

UPDATE alembic_version SET version_num='274950a4cd45' WHERE alembic_version.version_num = '46b05ea64319';

-- Running upgrade 274950a4cd45 -> 6c1f9a7e2d40

SELECT pg_advisory_xact_lock(62106420260715);

SET LOCAL lock_timeout = '60s';

SET LOCAL statement_timeout = '20min';

ALTER TABLE payment_transactions ALTER COLUMN idempotency_key TYPE VARCHAR(255);

ALTER TABLE payment_transactions ALTER COLUMN provider_payload TYPE JSONB USING provider_payload::jsonb;

ALTER TABLE subscription_plans ALTER COLUMN features TYPE JSONB USING features::jsonb;

ALTER TABLE subscription_plans ALTER COLUMN limits TYPE JSONB USING limits::jsonb;

DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_index i
                JOIN pg_class t ON t.oid = i.indrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = current_schema()
                  AND t.relname = 'subscription_plans'
                  AND i.indisunique
                  AND pg_get_indexdef(i.indexrelid)
                      ~ '\(\s*code\s*\)'
            ) THEN
                CREATE UNIQUE INDEX uq_subscription_plans_code_realtime
                ON subscription_plans (code);
            END IF;
        END $$;;

UPDATE notifications SET notification_type = 'SYSTEM' WHERE notification_type IS NULL;

UPDATE notifications SET is_read = FALSE WHERE is_read IS NULL;

ALTER TABLE notifications ALTER COLUMN notification_type SET NOT NULL;

ALTER TABLE notifications ALTER COLUMN is_read SET NOT NULL;

ALTER TABLE company_staff DROP CONSTRAINT IF EXISTS company_staff_company_id_fkey;

ALTER TABLE company_staff DROP CONSTRAINT IF EXISTS fk_company_staff_company;

ALTER TABLE company_staff ADD CONSTRAINT fk_company_staff_company FOREIGN KEY(company_id) REFERENCES loan_companies (id) ON DELETE CASCADE;

ALTER TABLE notifications DROP CONSTRAINT IF EXISTS notifications_user_id_fkey;

ALTER TABLE notifications DROP CONSTRAINT IF EXISTS fk_notifications_user;

ALTER TABLE notifications ADD CONSTRAINT fk_notifications_user FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE;

ALTER TABLE notifications DROP CONSTRAINT IF EXISTS notifications_related_loan_request_id_fkey;

ALTER TABLE notifications ADD CONSTRAINT notifications_related_loan_request_id_fkey FOREIGN KEY(related_loan_request_id) REFERENCES loan_requests (id) ON DELETE SET NULL;

ALTER TABLE notifications DROP CONSTRAINT IF EXISTS notifications_related_offer_id_fkey;

ALTER TABLE notifications ADD CONSTRAINT notifications_related_offer_id_fkey FOREIGN KEY(related_offer_id) REFERENCES loan_offers (id) ON DELETE SET NULL;

ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'HR_MANAGER';

ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'PERFORMANCE_MANAGER';

ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'RISK_MANAGER';

ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'IT_SUPPORT';

ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'PAYMENT';

ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'SUBSCRIPTION';

ALTER TABLE notifications ADD COLUMN actor_user_id UUID;

ALTER TABLE notifications ADD COLUMN company_id UUID;

ALTER TABLE notifications ADD COLUMN branch_id UUID;

ALTER TABLE notifications ADD COLUMN event_type VARCHAR(150) DEFAULT 'system.event' NOT NULL;

ALTER TABLE notifications ADD COLUMN action VARCHAR(40) DEFAULT 'view' NOT NULL;

ALTER TABLE notifications ADD COLUMN entity_type VARCHAR(120);

ALTER TABLE notifications ADD COLUMN entity_id VARCHAR(120);

ALTER TABLE notifications ADD COLUMN action_url VARCHAR(500);

ALTER TABLE notifications ADD COLUMN icon VARCHAR(80);

ALTER TABLE notifications ADD COLUMN priority VARCHAR(30) DEFAULT 'normal' NOT NULL;

ALTER TABLE notifications ADD COLUMN data JSONB DEFAULT '{}'::jsonb NOT NULL;

ALTER TABLE notifications ADD COLUMN deduplication_key VARCHAR(255);

ALTER TABLE notifications ADD COLUMN read_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE notifications ADD COLUMN is_archived BOOLEAN DEFAULT false NOT NULL;

ALTER TABLE notifications ADD COLUMN archived_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE notifications ADD CONSTRAINT fk_notifications_actor_user FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL;

ALTER TABLE notifications ADD CONSTRAINT fk_notifications_company FOREIGN KEY(company_id) REFERENCES loan_companies (id) ON DELETE SET NULL;

ALTER TABLE notifications ADD CONSTRAINT fk_notifications_branch FOREIGN KEY(branch_id) REFERENCES company_branches (id) ON DELETE SET NULL;

CREATE INDEX ix_notifications_user_id ON notifications (user_id);

CREATE INDEX ix_notifications_notification_type ON notifications (notification_type);

CREATE INDEX ix_notifications_actor_user_id ON notifications (actor_user_id);

CREATE INDEX ix_notifications_company_id ON notifications (company_id);

CREATE INDEX ix_notifications_branch_id ON notifications (branch_id);

CREATE INDEX ix_notifications_event_type ON notifications (event_type);

CREATE INDEX ix_notifications_entity_type ON notifications (entity_type);

CREATE INDEX ix_notifications_entity_id ON notifications (entity_id);

CREATE INDEX ix_notifications_priority ON notifications (priority);

CREATE INDEX ix_notifications_is_read ON notifications (is_read);

CREATE INDEX ix_notifications_is_archived ON notifications (is_archived);

CREATE INDEX ix_notifications_deduplication_key ON notifications (deduplication_key);

ALTER TABLE audit_logs ADD COLUMN company_id UUID;

ALTER TABLE audit_logs ADD COLUMN branch_id UUID;

ALTER TABLE audit_logs ADD COLUMN entity_type VARCHAR(150);

ALTER TABLE audit_logs ADD COLUMN actor_role VARCHAR(80);

ALTER TABLE audit_logs ADD COLUMN severity VARCHAR(30) DEFAULT 'info' NOT NULL;

ALTER TABLE audit_logs ADD COLUMN status VARCHAR(30) DEFAULT 'success' NOT NULL;

ALTER TABLE audit_logs ADD COLUMN before_data JSONB DEFAULT '{}'::jsonb NOT NULL;

ALTER TABLE audit_logs ADD COLUMN after_data JSONB DEFAULT '{}'::jsonb NOT NULL;

ALTER TABLE audit_logs ADD COLUMN changed_fields JSONB DEFAULT '[]'::jsonb NOT NULL;

ALTER TABLE audit_logs ADD COLUMN event_data JSONB DEFAULT '{}'::jsonb NOT NULL;

ALTER TABLE audit_logs ADD COLUMN request_id VARCHAR(100);

ALTER TABLE audit_logs ADD COLUMN user_agent VARCHAR(500);

ALTER TABLE audit_logs ADD COLUMN duration_ms INTEGER;

ALTER TABLE audit_logs DROP CONSTRAINT audit_logs_user_id_fkey;

ALTER TABLE audit_logs ADD CONSTRAINT fk_audit_logs_user FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL;

ALTER TABLE audit_logs ADD CONSTRAINT fk_audit_logs_company FOREIGN KEY(company_id) REFERENCES loan_companies (id) ON DELETE SET NULL;

ALTER TABLE audit_logs ADD CONSTRAINT fk_audit_logs_branch FOREIGN KEY(branch_id) REFERENCES company_branches (id) ON DELETE SET NULL;

CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id);

CREATE INDEX ix_audit_logs_table_name ON audit_logs (table_name);

CREATE INDEX ix_audit_logs_company_id ON audit_logs (company_id);

CREATE INDEX ix_audit_logs_branch_id ON audit_logs (branch_id);

CREATE INDEX ix_audit_logs_entity_type ON audit_logs (entity_type);

CREATE INDEX ix_audit_logs_action ON audit_logs (action);

CREATE INDEX ix_audit_logs_record_id ON audit_logs (record_id);

CREATE INDEX ix_audit_logs_severity ON audit_logs (severity);

CREATE INDEX ix_audit_logs_status ON audit_logs (status);

CREATE INDEX ix_audit_logs_request_id ON audit_logs (request_id);

CREATE TABLE employee_profiles (
    staff_id UUID NOT NULL, 
    company_id UUID NOT NULL, 
    branch_id UUID, 
    reports_to_staff_id UUID, 
    employee_number VARCHAR(80) NOT NULL, 
    job_title VARCHAR(150), 
    department VARCHAR(120), 
    employment_type VARCHAR(50) DEFAULT 'full_time' NOT NULL, 
    employment_status VARCHAR(50) DEFAULT 'active' NOT NULL, 
    hire_date DATE, 
    probation_end_date DATE, 
    termination_date DATE, 
    base_salary NUMERIC(15, 2), 
    currency VARCHAR(8) DEFAULT 'LSL' NOT NULL, 
    skills JSONB DEFAULT '[]'::jsonb NOT NULL, 
    target_config JSONB DEFAULT '{}'::jsonb NOT NULL, 
    notes TEXT, 
    is_manager BOOLEAN DEFAULT false NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(staff_id) REFERENCES company_staff (id) ON DELETE CASCADE, 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id) ON DELETE CASCADE, 
    FOREIGN KEY(branch_id) REFERENCES company_branches (id) ON DELETE SET NULL, 
    FOREIGN KEY(reports_to_staff_id) REFERENCES company_staff (id) ON DELETE SET NULL, 
    CONSTRAINT uq_employee_company_number UNIQUE (company_id, employee_number), 
    CONSTRAINT uq_employee_staff UNIQUE (staff_id)
);

CREATE INDEX ix_employee_profiles_staff_id ON employee_profiles (staff_id);

CREATE INDEX ix_employee_profiles_company_id ON employee_profiles (company_id);

CREATE INDEX ix_employee_profiles_branch_id ON employee_profiles (branch_id);

CREATE INDEX ix_employee_profiles_reports_to_staff_id ON employee_profiles (reports_to_staff_id);

CREATE INDEX ix_employee_profiles_department ON employee_profiles (department);

CREATE INDEX ix_employee_profiles_employment_status ON employee_profiles (employment_status);

CREATE TABLE performance_goals (
    employee_id UUID NOT NULL, 
    company_id UUID NOT NULL, 
    branch_id UUID, 
    created_by_user_id UUID, 
    title VARCHAR(200) NOT NULL, 
    description TEXT, 
    category VARCHAR(100) DEFAULT 'general' NOT NULL, 
    target_value NUMERIC(15, 3) DEFAULT '100' NOT NULL, 
    current_value NUMERIC(15, 3) DEFAULT '0' NOT NULL, 
    unit VARCHAR(50) DEFAULT 'percent' NOT NULL, 
    weight NUMERIC(6, 3) DEFAULT '1' NOT NULL, 
    period_start DATE NOT NULL, 
    period_end DATE NOT NULL, 
    status VARCHAR(40) DEFAULT 'active' NOT NULL, 
    completed_at TIMESTAMP WITHOUT TIME ZONE, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(employee_id) REFERENCES employee_profiles (id) ON DELETE CASCADE, 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id) ON DELETE CASCADE, 
    FOREIGN KEY(branch_id) REFERENCES company_branches (id) ON DELETE SET NULL, 
    FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_performance_goals_employee_id ON performance_goals (employee_id);

CREATE INDEX ix_performance_goals_company_id ON performance_goals (company_id);

CREATE INDEX ix_performance_goals_branch_id ON performance_goals (branch_id);

CREATE INDEX ix_performance_goals_category ON performance_goals (category);

CREATE INDEX ix_performance_goals_status ON performance_goals (status);

CREATE TABLE performance_reviews (
    employee_id UUID NOT NULL, 
    reviewer_staff_id UUID, 
    company_id UUID NOT NULL, 
    branch_id UUID, 
    period_start DATE NOT NULL, 
    period_end DATE NOT NULL, 
    overall_score NUMERIC(6, 2) NOT NULL, 
    rating VARCHAR(50) NOT NULL, 
    status VARCHAR(40) DEFAULT 'completed' NOT NULL, 
    strengths TEXT, 
    improvements TEXT, 
    comments TEXT, 
    metrics JSONB DEFAULT '{}'::jsonb NOT NULL, 
    employee_acknowledged_at TIMESTAMP WITHOUT TIME ZONE, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(employee_id) REFERENCES employee_profiles (id) ON DELETE CASCADE, 
    FOREIGN KEY(reviewer_staff_id) REFERENCES company_staff (id) ON DELETE SET NULL, 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id) ON DELETE CASCADE, 
    FOREIGN KEY(branch_id) REFERENCES company_branches (id) ON DELETE SET NULL
);

CREATE INDEX ix_performance_reviews_employee_id ON performance_reviews (employee_id);

CREATE INDEX ix_performance_reviews_reviewer_staff_id ON performance_reviews (reviewer_staff_id);

CREATE INDEX ix_performance_reviews_company_id ON performance_reviews (company_id);

CREATE INDEX ix_performance_reviews_branch_id ON performance_reviews (branch_id);

CREATE INDEX ix_performance_reviews_rating ON performance_reviews (rating);

CREATE INDEX ix_performance_reviews_status ON performance_reviews (status);

CREATE TABLE system_error_logs (
    request_id VARCHAR(100), 
    fingerprint VARCHAR(128) NOT NULL, 
    user_id UUID, 
    company_id UUID, 
    branch_id UUID, 
    method VARCHAR(20), 
    path VARCHAR(500) NOT NULL, 
    status_code INTEGER DEFAULT '500' NOT NULL, 
    error_type VARCHAR(200) NOT NULL, 
    message TEXT NOT NULL, 
    stack_trace TEXT, 
    severity VARCHAR(30) DEFAULT 'error' NOT NULL, 
    environment VARCHAR(50), 
    user_agent VARCHAR(500), 
    context JSONB DEFAULT '{}'::jsonb NOT NULL, 
    occurrence_count INTEGER DEFAULT '1' NOT NULL, 
    first_seen_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    last_seen_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    is_resolved BOOLEAN DEFAULT false NOT NULL, 
    resolved_at TIMESTAMP WITHOUT TIME ZONE, 
    resolved_by_user_id UUID, 
    resolution_notes TEXT, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id) ON DELETE SET NULL, 
    FOREIGN KEY(branch_id) REFERENCES company_branches (id) ON DELETE SET NULL, 
    FOREIGN KEY(resolved_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
    UNIQUE (fingerprint)
);

CREATE INDEX ix_system_error_logs_request_id ON system_error_logs (request_id);

CREATE INDEX ix_system_error_logs_fingerprint ON system_error_logs (fingerprint);

CREATE INDEX ix_system_error_logs_user_id ON system_error_logs (user_id);

CREATE INDEX ix_system_error_logs_company_id ON system_error_logs (company_id);

CREATE INDEX ix_system_error_logs_branch_id ON system_error_logs (branch_id);

CREATE INDEX ix_system_error_logs_path ON system_error_logs (path);

CREATE INDEX ix_system_error_logs_status_code ON system_error_logs (status_code);

CREATE INDEX ix_system_error_logs_error_type ON system_error_logs (error_type);

CREATE INDEX ix_system_error_logs_severity ON system_error_logs (severity);

CREATE INDEX ix_system_error_logs_is_resolved ON system_error_logs (is_resolved);

UPDATE alembic_version SET version_num='6c1f9a7e2d40' WHERE alembic_version.version_num = '274950a4cd45';

-- Running upgrade 6c1f9a7e2d40 -> 3957062b7c66

UPDATE alembic_version SET version_num='3957062b7c66' WHERE alembic_version.version_num = '6c1f9a7e2d40';

-- Running upgrade 3957062b7c66 -> 8d2f4a1b7c90

SELECT pg_advisory_xact_lock(62106420260716);

SET LOCAL lock_timeout = '60s';

SET LOCAL statement_timeout = '20min';

CREATE TABLE managed_files (
    owner_user_id UUID, 
    company_id UUID, 
    branch_id UUID, 
    reference VARCHAR(40) NOT NULL, 
    original_name VARCHAR(255) NOT NULL, 
    stored_name VARCHAR(255) NOT NULL, 
    storage_key VARCHAR(700) NOT NULL, 
    storage_provider VARCHAR(30) NOT NULL, 
    mime_type VARCHAR(150) NOT NULL, 
    extension VARCHAR(30), 
    size_bytes BIGINT NOT NULL, 
    checksum_sha256 VARCHAR(64) NOT NULL, 
    category VARCHAR(80) NOT NULL, 
    visibility VARCHAR(40) NOT NULL, 
    description TEXT, 
    linked_entity_type VARCHAR(100), 
    linked_entity_id VARCHAR(120), 
    is_confidential BOOLEAN NOT NULL, 
    is_deleted BOOLEAN NOT NULL, 
    deleted_at TIMESTAMP WITHOUT TIME ZONE, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id) ON DELETE CASCADE, 
    FOREIGN KEY(branch_id) REFERENCES company_branches (id) ON DELETE SET NULL, 
    UNIQUE (reference), 
    UNIQUE (storage_key)
);

CREATE INDEX ix_managed_files_owner_user_id ON managed_files (owner_user_id);

CREATE INDEX ix_managed_files_company_id ON managed_files (company_id);

CREATE INDEX ix_managed_files_branch_id ON managed_files (branch_id);

CREATE INDEX ix_managed_files_reference ON managed_files (reference);

CREATE INDEX ix_managed_files_checksum_sha256 ON managed_files (checksum_sha256);

CREATE INDEX ix_managed_files_category ON managed_files (category);

CREATE INDEX ix_managed_files_visibility ON managed_files (visibility);

CREATE INDEX ix_managed_files_linked_entity_type ON managed_files (linked_entity_type);

CREATE INDEX ix_managed_files_linked_entity_id ON managed_files (linked_entity_id);

CREATE INDEX ix_managed_files_is_deleted ON managed_files (is_deleted);

CREATE TABLE chat_conversations (
    reference VARCHAR(40) NOT NULL, 
    company_id UUID, 
    branch_id UUID, 
    created_by_user_id UUID, 
    title VARCHAR(200), 
    conversation_type VARCHAR(40) NOT NULL, 
    context_type VARCHAR(80), 
    context_id VARCHAR(120), 
    is_group BOOLEAN NOT NULL, 
    is_archived BOOLEAN NOT NULL, 
    last_message_at TIMESTAMP WITHOUT TIME ZONE, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id) ON DELETE SET NULL, 
    FOREIGN KEY(branch_id) REFERENCES company_branches (id) ON DELETE SET NULL, 
    FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
    UNIQUE (reference)
);

CREATE INDEX ix_chat_conversations_reference ON chat_conversations (reference);

CREATE INDEX ix_chat_conversations_company_id ON chat_conversations (company_id);

CREATE INDEX ix_chat_conversations_branch_id ON chat_conversations (branch_id);

CREATE INDEX ix_chat_conversations_created_by_user_id ON chat_conversations (created_by_user_id);

CREATE INDEX ix_chat_conversations_conversation_type ON chat_conversations (conversation_type);

CREATE INDEX ix_chat_conversations_context_type ON chat_conversations (context_type);

CREATE INDEX ix_chat_conversations_context_id ON chat_conversations (context_id);

CREATE INDEX ix_chat_conversations_is_archived ON chat_conversations (is_archived);

CREATE INDEX ix_chat_conversations_last_message_at ON chat_conversations (last_message_at);

CREATE TABLE chat_participants (
    conversation_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    participant_role VARCHAR(80), 
    is_admin BOOLEAN NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    joined_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    last_read_at TIMESTAMP WITHOUT TIME ZONE, 
    muted_until TIMESTAMP WITHOUT TIME ZONE, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(conversation_id) REFERENCES chat_conversations (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_chat_participant_conversation_user UNIQUE (conversation_id, user_id)
);

CREATE INDEX ix_chat_participants_conversation_id ON chat_participants (conversation_id);

CREATE INDEX ix_chat_participants_user_id ON chat_participants (user_id);

CREATE INDEX ix_chat_participants_is_active ON chat_participants (is_active);

CREATE TABLE chat_messages (
    conversation_id UUID NOT NULL, 
    sender_user_id UUID, 
    company_id UUID, 
    branch_id UUID, 
    reply_to_message_id UUID, 
    message_type VARCHAR(30) NOT NULL, 
    body TEXT, 
    client_message_id VARCHAR(100) NOT NULL, 
    metadata_json JSONB NOT NULL, 
    edited_at TIMESTAMP WITHOUT TIME ZONE, 
    deleted_at TIMESTAMP WITHOUT TIME ZONE, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(conversation_id) REFERENCES chat_conversations (id) ON DELETE CASCADE, 
    FOREIGN KEY(sender_user_id) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id) ON DELETE SET NULL, 
    FOREIGN KEY(branch_id) REFERENCES company_branches (id) ON DELETE SET NULL, 
    FOREIGN KEY(reply_to_message_id) REFERENCES chat_messages (id) ON DELETE SET NULL, 
    CONSTRAINT uq_chat_message_sender_client_id UNIQUE (sender_user_id, client_message_id)
);

CREATE INDEX ix_chat_messages_conversation_id ON chat_messages (conversation_id);

CREATE INDEX ix_chat_messages_sender_user_id ON chat_messages (sender_user_id);

CREATE INDEX ix_chat_messages_company_id ON chat_messages (company_id);

CREATE INDEX ix_chat_messages_branch_id ON chat_messages (branch_id);

CREATE INDEX ix_chat_messages_message_type ON chat_messages (message_type);

CREATE INDEX ix_chat_messages_deleted_at ON chat_messages (deleted_at);

CREATE TABLE chat_message_attachments (
    message_id UUID NOT NULL, 
    file_id UUID NOT NULL, 
    caption VARCHAR(500), 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(message_id) REFERENCES chat_messages (id) ON DELETE CASCADE, 
    FOREIGN KEY(file_id) REFERENCES managed_files (id) ON DELETE CASCADE, 
    CONSTRAINT uq_chat_message_file UNIQUE (message_id, file_id)
);

CREATE INDEX ix_chat_message_attachments_message_id ON chat_message_attachments (message_id);

CREATE INDEX ix_chat_message_attachments_file_id ON chat_message_attachments (file_id);

CREATE TABLE accounting_accounts (
    scope_key VARCHAR(80) NOT NULL, 
    scope_type VARCHAR(20) NOT NULL, 
    company_id UUID, 
    branch_id UUID, 
    parent_id UUID, 
    code VARCHAR(30) NOT NULL, 
    name VARCHAR(180) NOT NULL, 
    account_type VARCHAR(30) NOT NULL, 
    normal_balance VARCHAR(10) NOT NULL, 
    description TEXT, 
    is_system BOOLEAN NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id) ON DELETE CASCADE, 
    FOREIGN KEY(branch_id) REFERENCES company_branches (id) ON DELETE SET NULL, 
    FOREIGN KEY(parent_id) REFERENCES accounting_accounts (id) ON DELETE SET NULL, 
    CONSTRAINT uq_accounting_scope_code UNIQUE (scope_key, code)
);

CREATE INDEX ix_accounting_accounts_scope_key ON accounting_accounts (scope_key);

CREATE INDEX ix_accounting_accounts_scope_type ON accounting_accounts (scope_type);

CREATE INDEX ix_accounting_accounts_company_id ON accounting_accounts (company_id);

CREATE INDEX ix_accounting_accounts_branch_id ON accounting_accounts (branch_id);

CREATE INDEX ix_accounting_accounts_account_type ON accounting_accounts (account_type);

CREATE INDEX ix_accounting_accounts_is_active ON accounting_accounts (is_active);

CREATE TABLE journal_entries (
    scope_key VARCHAR(80) NOT NULL, 
    scope_type VARCHAR(20) NOT NULL, 
    company_id UUID, 
    branch_id UUID, 
    created_by_user_id UUID, 
    posted_by_user_id UUID, 
    entry_number VARCHAR(60) NOT NULL, 
    entry_date DATE NOT NULL, 
    description TEXT NOT NULL, 
    reference_type VARCHAR(80), 
    reference_id VARCHAR(120), 
    status VARCHAR(20) NOT NULL, 
    total_debit NUMERIC(18, 2) NOT NULL, 
    total_credit NUMERIC(18, 2) NOT NULL, 
    posted_at TIMESTAMP WITHOUT TIME ZONE, 
    voided_at TIMESTAMP WITHOUT TIME ZONE, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id) ON DELETE CASCADE, 
    FOREIGN KEY(branch_id) REFERENCES company_branches (id) ON DELETE SET NULL, 
    FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(posted_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT uq_journal_scope_number UNIQUE (scope_key, entry_number), 
    CONSTRAINT uq_journal_scope_reference UNIQUE (scope_key, reference_type, reference_id)
);

CREATE INDEX ix_journal_entries_scope_key ON journal_entries (scope_key);

CREATE INDEX ix_journal_entries_scope_type ON journal_entries (scope_type);

CREATE INDEX ix_journal_entries_company_id ON journal_entries (company_id);

CREATE INDEX ix_journal_entries_branch_id ON journal_entries (branch_id);

CREATE INDEX ix_journal_entries_entry_number ON journal_entries (entry_number);

CREATE INDEX ix_journal_entries_entry_date ON journal_entries (entry_date);

CREATE INDEX ix_journal_entries_reference_type ON journal_entries (reference_type);

CREATE INDEX ix_journal_entries_reference_id ON journal_entries (reference_id);

CREATE INDEX ix_journal_entries_status ON journal_entries (status);

CREATE TABLE journal_lines (
    journal_entry_id UUID NOT NULL, 
    account_id UUID NOT NULL, 
    description VARCHAR(500), 
    debit NUMERIC(18, 2) NOT NULL, 
    credit NUMERIC(18, 2) NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(journal_entry_id) REFERENCES journal_entries (id) ON DELETE CASCADE, 
    FOREIGN KEY(account_id) REFERENCES accounting_accounts (id) ON DELETE RESTRICT
);

CREATE INDEX ix_journal_lines_journal_entry_id ON journal_lines (journal_entry_id);

CREATE INDEX ix_journal_lines_account_id ON journal_lines (account_id);

CREATE TABLE report_schedules (
    scope_type VARCHAR(20) NOT NULL, 
    company_id UUID, 
    branch_id UUID, 
    created_by_user_id UUID, 
    name VARCHAR(180) NOT NULL, 
    report_type VARCHAR(50) NOT NULL, 
    frequency VARCHAR(20) NOT NULL, 
    output_format VARCHAR(10) NOT NULL, 
    recipients JSONB NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    next_run_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    last_run_at TIMESTAMP WITHOUT TIME ZONE, 
    last_status VARCHAR(30), 
    last_error TEXT, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id) ON DELETE CASCADE, 
    FOREIGN KEY(branch_id) REFERENCES company_branches (id) ON DELETE CASCADE, 
    FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_report_schedules_scope_type ON report_schedules (scope_type);

CREATE INDEX ix_report_schedules_company_id ON report_schedules (company_id);

CREATE INDEX ix_report_schedules_branch_id ON report_schedules (branch_id);

CREATE INDEX ix_report_schedules_report_type ON report_schedules (report_type);

CREATE INDEX ix_report_schedules_frequency ON report_schedules (frequency);

CREATE INDEX ix_report_schedules_is_active ON report_schedules (is_active);

CREATE INDEX ix_report_schedules_next_run_at ON report_schedules (next_run_at);

CREATE TABLE generated_reports (
    reference VARCHAR(50) NOT NULL, 
    scope_type VARCHAR(20) NOT NULL, 
    company_id UUID, 
    branch_id UUID, 
    schedule_id UUID, 
    generated_by_user_id UUID, 
    file_id UUID, 
    title VARCHAR(240) NOT NULL, 
    report_type VARCHAR(50) NOT NULL, 
    output_format VARCHAR(10) NOT NULL, 
    period_start DATE NOT NULL, 
    period_end DATE NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    metrics JSONB NOT NULL, 
    error_message TEXT, 
    generated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    created_by VARCHAR(36), 
    updated_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(company_id) REFERENCES loan_companies (id) ON DELETE SET NULL, 
    FOREIGN KEY(branch_id) REFERENCES company_branches (id) ON DELETE SET NULL, 
    FOREIGN KEY(schedule_id) REFERENCES report_schedules (id) ON DELETE SET NULL, 
    FOREIGN KEY(generated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(file_id) REFERENCES managed_files (id) ON DELETE SET NULL, 
    UNIQUE (reference)
);

CREATE INDEX ix_generated_reports_reference ON generated_reports (reference);

CREATE INDEX ix_generated_reports_scope_type ON generated_reports (scope_type);

CREATE INDEX ix_generated_reports_company_id ON generated_reports (company_id);

CREATE INDEX ix_generated_reports_branch_id ON generated_reports (branch_id);

CREATE INDEX ix_generated_reports_schedule_id ON generated_reports (schedule_id);

CREATE INDEX ix_generated_reports_report_type ON generated_reports (report_type);

CREATE INDEX ix_generated_reports_status ON generated_reports (status);

UPDATE alembic_version SET version_num='8d2f4a1b7c90' WHERE alembic_version.version_num = '3957062b7c66';

-- Running upgrade 8d2f4a1b7c90 -> b84d1f2a9c30

ALTER TABLE performance_goals ADD COLUMN IF NOT EXISTS created_by VARCHAR(36);

DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'system_error_logs_fingerprint_key'
                  AND conrelid = 'system_error_logs'::regclass
            ) THEN
                IF EXISTS (
                    SELECT 1
                    FROM pg_class index_class
                    JOIN pg_index index_info
                      ON index_info.indexrelid = index_class.oid
                    JOIN pg_class table_class
                      ON table_class.oid = index_info.indrelid
                    WHERE index_class.relname = 'ix_system_error_logs_fingerprint'
                      AND table_class.relname = 'system_error_logs'
                      AND index_info.indisunique
                ) THEN
                    ALTER TABLE system_error_logs
                    ADD CONSTRAINT system_error_logs_fingerprint_key
                    UNIQUE USING INDEX ix_system_error_logs_fingerprint;
                ELSE
                    ALTER TABLE system_error_logs
                    ADD CONSTRAINT system_error_logs_fingerprint_key
                    UNIQUE (fingerprint);
                END IF;
            END IF;
        END
        $$;;

DO $$
        DECLARE
            target_index_oid OID;
        BEGIN
            SELECT c.oid
              INTO target_index_oid
              FROM pg_class c
             WHERE c.relname = 'ix_system_error_logs_fingerprint'
               AND c.relkind = 'i';

            IF target_index_oid IS NOT NULL
               AND NOT EXISTS (
                    SELECT 1
                      FROM pg_constraint
                     WHERE conindid = target_index_oid
               ) THEN
                DROP INDEX ix_system_error_logs_fingerprint;
            END IF;
        END
        $$;;

UPDATE alembic_version SET version_num='b84d1f2a9c30' WHERE alembic_version.version_num = '8d2f4a1b7c90';

-- Running upgrade b84d1f2a9c30 -> d4e7b6c1a930

SELECT pg_advisory_xact_lock(62106420260717);

SET LOCAL lock_timeout = '60s';

SET LOCAL statement_timeout = '20min';

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_client_loan_borrower_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_client_company_loan_borrower_id'
                ) IS NULL THEN
                    ALTER INDEX ix_client_loan_borrower_id
                    RENAME TO ix_client_company_loan_borrower_id;
                ELSE
                    DROP INDEX ix_client_loan_borrower_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_client_loan_branch_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_client_company_loan_branch_id'
                ) IS NULL THEN
                    ALTER INDEX ix_client_loan_branch_id
                    RENAME TO ix_client_company_loan_branch_id;
                ELSE
                    DROP INDEX ix_client_loan_branch_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_client_loan_company_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_client_company_loan_company_id'
                ) IS NULL THEN
                    ALTER INDEX ix_client_loan_company_id
                    RENAME TO ix_client_company_loan_company_id;
                ELSE
                    DROP INDEX ix_client_loan_company_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_loan_offers_request_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_loan_offers_loan_request_id'
                ) IS NULL THEN
                    ALTER INDEX ix_loan_offers_request_id
                    RENAME TO ix_loan_offers_loan_request_id;
                ELSE
                    DROP INDEX ix_loan_offers_request_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_marketplace_unlock_company'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_marketplace_unlocks_company_id'
                ) IS NULL THEN
                    ALTER INDEX ix_marketplace_unlock_company
                    RENAME TO ix_marketplace_unlocks_company_id;
                ELSE
                    DROP INDEX ix_marketplace_unlock_company;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_marketplace_unlock_request'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_marketplace_unlocks_loan_request_id'
                ) IS NULL THEN
                    ALTER INDEX ix_marketplace_unlock_request
                    RENAME TO ix_marketplace_unlocks_loan_request_id;
                ELSE
                    DROP INDEX ix_marketplace_unlock_request;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_payment_allocation_installment'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_payment_allocations_installment_id'
                ) IS NULL THEN
                    ALTER INDEX ix_payment_allocation_installment
                    RENAME TO ix_payment_allocations_installment_id;
                ELSE
                    DROP INDEX ix_payment_allocation_installment;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_payment_allocation_payment'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_payment_allocations_payment_id'
                ) IS NULL THEN
                    ALTER INDEX ix_payment_allocation_payment
                    RENAME TO ix_payment_allocations_payment_id;
                ELSE
                    DROP INDEX ix_payment_allocation_payment;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_payment_borrower_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_payment_transactions_borrower_id'
                ) IS NULL THEN
                    ALTER INDEX ix_payment_borrower_id
                    RENAME TO ix_payment_transactions_borrower_id;
                ELSE
                    DROP INDEX ix_payment_borrower_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_payment_company_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_payment_transactions_company_id'
                ) IS NULL THEN
                    ALTER INDEX ix_payment_company_id
                    RENAME TO ix_payment_transactions_company_id;
                ELSE
                    DROP INDEX ix_payment_company_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_payment_idempotency'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_payment_transactions_idempotency_key'
                ) IS NULL THEN
                    ALTER INDEX ix_payment_idempotency
                    RENAME TO ix_payment_transactions_idempotency_key;
                ELSE
                    DROP INDEX ix_payment_idempotency;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_payment_loan_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_payment_transactions_loan_id'
                ) IS NULL THEN
                    ALTER INDEX ix_payment_loan_id
                    RENAME TO ix_payment_transactions_loan_id;
                ELSE
                    DROP INDEX ix_payment_loan_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_payment_loan_request_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_payment_transactions_loan_request_id'
                ) IS NULL THEN
                    ALTER INDEX ix_payment_loan_request_id
                    RENAME TO ix_payment_transactions_loan_request_id;
                ELSE
                    DROP INDEX ix_payment_loan_request_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_payment_provider_reference'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_payment_transactions_provider_reference'
                ) IS NULL THEN
                    ALTER INDEX ix_payment_provider_reference
                    RENAME TO ix_payment_transactions_provider_reference;
                ELSE
                    DROP INDEX ix_payment_provider_reference;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_repayment_installment_due'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_repayment_installments_due_date'
                ) IS NULL THEN
                    ALTER INDEX ix_repayment_installment_due
                    RENAME TO ix_repayment_installments_due_date;
                ELSE
                    DROP INDEX ix_repayment_installment_due;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_repayment_installment_loan'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_repayment_installments_loan_id'
                ) IS NULL THEN
                    ALTER INDEX ix_repayment_installment_loan
                    RENAME TO ix_repayment_installments_loan_id;
                ELSE
                    DROP INDEX ix_repayment_installment_loan;
                END IF;
            END IF;
        END
        $$;;

DO $$
        DECLARE
            item RECORD;
        BEGIN
            FOR item IN
                SELECT constraint_row.conname
                  FROM pg_constraint AS constraint_row
                  JOIN pg_class AS source_table
                    ON source_table.oid = constraint_row.conrelid
                  JOIN pg_namespace AS source_schema
                    ON source_schema.oid = source_table.relnamespace
                 WHERE constraint_row.contype = 'f'
                   AND source_schema.nspname = current_schema()
                   AND source_table.relname = 'loan_requests'
                   AND constraint_row.confrelid =
                       'loan_offers'::regclass
                   AND EXISTS (
                        SELECT 1
                          FROM unnest(constraint_row.conkey)
                               AS key_column(attnum)
                          JOIN pg_attribute AS attribute_row
                            ON attribute_row.attrelid =
                               constraint_row.conrelid
                           AND attribute_row.attnum =
                               key_column.attnum
                         WHERE attribute_row.attname =
                               'selected_offer_id'
                   )
            LOOP
                EXECUTE format(
                    'ALTER TABLE loan_requests '
                    'DROP CONSTRAINT %I',
                    item.conname
                );
            END LOOP;
        END
        $$;;

ALTER TABLE loan_requests ADD CONSTRAINT loan_requests_selected_offer_id_fkey FOREIGN KEY(selected_offer_id) REFERENCES loan_offers (id) ON DELETE SET NULL;

UPDATE alembic_version SET version_num='d4e7b6c1a930' WHERE alembic_version.version_num = 'b84d1f2a9c30';

-- Running upgrade d4e7b6c1a930 -> f1a9c4e7b620

SELECT pg_advisory_xact_lock(62106420260721);

SET LOCAL lock_timeout = '60s';

SET LOCAL statement_timeout = '20min';

ALTER TABLE users ADD COLUMN last_seen_at TIMESTAMP WITHOUT TIME ZONE;

CREATE INDEX ix_users_last_seen_at ON users (last_seen_at);

ALTER TABLE chat_messages ADD COLUMN body_ciphertext TEXT;

ALTER TABLE chat_messages ADD COLUMN body_nonce VARCHAR(64);

ALTER TABLE chat_messages ADD COLUMN encryption_version VARCHAR(20);

ALTER TABLE managed_files ADD COLUMN detected_mime_type VARCHAR(150);

ALTER TABLE managed_files ADD COLUMN is_encrypted BOOLEAN DEFAULT false NOT NULL;

ALTER TABLE managed_files ADD COLUMN encryption_nonce VARCHAR(64);

ALTER TABLE managed_files ADD COLUMN encryption_version VARCHAR(20);

ALTER TABLE managed_files ADD COLUMN scan_status VARCHAR(30) DEFAULT 'legacy' NOT NULL;

ALTER TABLE managed_files ADD COLUMN quarantined_reason TEXT;

CREATE INDEX ix_managed_files_scan_status ON managed_files (scan_status);

UPDATE managed_files SET detected_mime_type = mime_type WHERE detected_mime_type IS NULL;

UPDATE alembic_version SET version_num='f1a9c4e7b620' WHERE alembic_version.version_num = 'd4e7b6c1a930';

COMMIT;

