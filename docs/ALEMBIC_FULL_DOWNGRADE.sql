BEGIN;

-- Running downgrade f1a9c4e7b620 -> d4e7b6c1a930

DROP INDEX ix_managed_files_scan_status;

ALTER TABLE managed_files DROP COLUMN quarantined_reason;

ALTER TABLE managed_files DROP COLUMN scan_status;

ALTER TABLE managed_files DROP COLUMN encryption_version;

ALTER TABLE managed_files DROP COLUMN encryption_nonce;

ALTER TABLE managed_files DROP COLUMN is_encrypted;

ALTER TABLE managed_files DROP COLUMN detected_mime_type;

ALTER TABLE chat_messages DROP COLUMN encryption_version;

ALTER TABLE chat_messages DROP COLUMN body_nonce;

ALTER TABLE chat_messages DROP COLUMN body_ciphertext;

DROP INDEX ix_users_last_seen_at;

ALTER TABLE users DROP COLUMN last_seen_at;

UPDATE alembic_version SET version_num='d4e7b6c1a930' WHERE alembic_version.version_num = 'f1a9c4e7b620';

-- Running downgrade d4e7b6c1a930 -> b84d1f2a9c30

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

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_repayment_installments_loan_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_repayment_installment_loan'
                ) IS NULL THEN
                    ALTER INDEX ix_repayment_installments_loan_id
                    RENAME TO ix_repayment_installment_loan;
                ELSE
                    DROP INDEX ix_repayment_installments_loan_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_repayment_installments_due_date'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_repayment_installment_due'
                ) IS NULL THEN
                    ALTER INDEX ix_repayment_installments_due_date
                    RENAME TO ix_repayment_installment_due;
                ELSE
                    DROP INDEX ix_repayment_installments_due_date;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_payment_transactions_provider_reference'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_payment_provider_reference'
                ) IS NULL THEN
                    ALTER INDEX ix_payment_transactions_provider_reference
                    RENAME TO ix_payment_provider_reference;
                ELSE
                    DROP INDEX ix_payment_transactions_provider_reference;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_payment_transactions_loan_request_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_payment_loan_request_id'
                ) IS NULL THEN
                    ALTER INDEX ix_payment_transactions_loan_request_id
                    RENAME TO ix_payment_loan_request_id;
                ELSE
                    DROP INDEX ix_payment_transactions_loan_request_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_payment_transactions_loan_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_payment_loan_id'
                ) IS NULL THEN
                    ALTER INDEX ix_payment_transactions_loan_id
                    RENAME TO ix_payment_loan_id;
                ELSE
                    DROP INDEX ix_payment_transactions_loan_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_payment_transactions_idempotency_key'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_payment_idempotency'
                ) IS NULL THEN
                    ALTER INDEX ix_payment_transactions_idempotency_key
                    RENAME TO ix_payment_idempotency;
                ELSE
                    DROP INDEX ix_payment_transactions_idempotency_key;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_payment_transactions_company_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_payment_company_id'
                ) IS NULL THEN
                    ALTER INDEX ix_payment_transactions_company_id
                    RENAME TO ix_payment_company_id;
                ELSE
                    DROP INDEX ix_payment_transactions_company_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_payment_transactions_borrower_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_payment_borrower_id'
                ) IS NULL THEN
                    ALTER INDEX ix_payment_transactions_borrower_id
                    RENAME TO ix_payment_borrower_id;
                ELSE
                    DROP INDEX ix_payment_transactions_borrower_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_payment_allocations_payment_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_payment_allocation_payment'
                ) IS NULL THEN
                    ALTER INDEX ix_payment_allocations_payment_id
                    RENAME TO ix_payment_allocation_payment;
                ELSE
                    DROP INDEX ix_payment_allocations_payment_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_payment_allocations_installment_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_payment_allocation_installment'
                ) IS NULL THEN
                    ALTER INDEX ix_payment_allocations_installment_id
                    RENAME TO ix_payment_allocation_installment;
                ELSE
                    DROP INDEX ix_payment_allocations_installment_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_marketplace_unlocks_loan_request_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_marketplace_unlock_request'
                ) IS NULL THEN
                    ALTER INDEX ix_marketplace_unlocks_loan_request_id
                    RENAME TO ix_marketplace_unlock_request;
                ELSE
                    DROP INDEX ix_marketplace_unlocks_loan_request_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_marketplace_unlocks_company_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_marketplace_unlock_company'
                ) IS NULL THEN
                    ALTER INDEX ix_marketplace_unlocks_company_id
                    RENAME TO ix_marketplace_unlock_company;
                ELSE
                    DROP INDEX ix_marketplace_unlocks_company_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_loan_offers_loan_request_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_loan_offers_request_id'
                ) IS NULL THEN
                    ALTER INDEX ix_loan_offers_loan_request_id
                    RENAME TO ix_loan_offers_request_id;
                ELSE
                    DROP INDEX ix_loan_offers_loan_request_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_client_company_loan_company_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_client_loan_company_id'
                ) IS NULL THEN
                    ALTER INDEX ix_client_company_loan_company_id
                    RENAME TO ix_client_loan_company_id;
                ELSE
                    DROP INDEX ix_client_company_loan_company_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_client_company_loan_branch_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_client_loan_branch_id'
                ) IS NULL THEN
                    ALTER INDEX ix_client_company_loan_branch_id
                    RENAME TO ix_client_loan_branch_id;
                ELSE
                    DROP INDEX ix_client_company_loan_branch_id;
                END IF;
            END IF;
        END
        $$;;

DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.ix_client_company_loan_borrower_id'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.ix_client_loan_borrower_id'
                ) IS NULL THEN
                    ALTER INDEX ix_client_company_loan_borrower_id
                    RENAME TO ix_client_loan_borrower_id;
                ELSE
                    DROP INDEX ix_client_company_loan_borrower_id;
                END IF;
            END IF;
        END
        $$;;

UPDATE alembic_version SET version_num='b84d1f2a9c30' WHERE alembic_version.version_num = 'd4e7b6c1a930';

-- Running downgrade b84d1f2a9c30 -> 8d2f4a1b7c90

CREATE INDEX IF NOT EXISTS ix_system_error_logs_fingerprint ON system_error_logs (fingerprint);

UPDATE alembic_version SET version_num='8d2f4a1b7c90' WHERE alembic_version.version_num = 'b84d1f2a9c30';

-- Running downgrade 8d2f4a1b7c90 -> 3957062b7c66

DROP TABLE generated_reports;

DROP TABLE report_schedules;

DROP TABLE journal_lines;

DROP TABLE journal_entries;

DROP TABLE accounting_accounts;

DROP TABLE chat_message_attachments;

DROP TABLE chat_messages;

DROP TABLE chat_participants;

DROP TABLE chat_conversations;

DROP TABLE managed_files;

UPDATE alembic_version SET version_num='3957062b7c66' WHERE alembic_version.version_num = '8d2f4a1b7c90';

-- Running downgrade 3957062b7c66 -> 6c1f9a7e2d40

UPDATE alembic_version SET version_num='6c1f9a7e2d40' WHERE alembic_version.version_num = '3957062b7c66';

-- Running downgrade 6c1f9a7e2d40 -> 274950a4cd45

DROP TABLE system_error_logs;

DROP TABLE performance_reviews;

DROP TABLE performance_goals;

DROP TABLE employee_profiles;

DROP INDEX ix_audit_logs_request_id;

DROP INDEX ix_audit_logs_status;

DROP INDEX ix_audit_logs_severity;

DROP INDEX ix_audit_logs_table_name;

DROP INDEX ix_audit_logs_user_id;

DROP INDEX ix_audit_logs_record_id;

DROP INDEX ix_audit_logs_action;

DROP INDEX ix_audit_logs_entity_type;

DROP INDEX ix_audit_logs_branch_id;

DROP INDEX ix_audit_logs_company_id;

ALTER TABLE audit_logs DROP CONSTRAINT fk_audit_logs_branch;

ALTER TABLE audit_logs DROP CONSTRAINT fk_audit_logs_company;

ALTER TABLE audit_logs DROP CONSTRAINT fk_audit_logs_user;

ALTER TABLE audit_logs ADD CONSTRAINT audit_logs_user_id_fkey FOREIGN KEY(user_id) REFERENCES users (id);

ALTER TABLE audit_logs DROP COLUMN duration_ms;

ALTER TABLE audit_logs DROP COLUMN user_agent;

ALTER TABLE audit_logs DROP COLUMN request_id;

ALTER TABLE audit_logs DROP COLUMN event_data;

ALTER TABLE audit_logs DROP COLUMN changed_fields;

ALTER TABLE audit_logs DROP COLUMN after_data;

ALTER TABLE audit_logs DROP COLUMN before_data;

ALTER TABLE audit_logs DROP COLUMN status;

ALTER TABLE audit_logs DROP COLUMN severity;

ALTER TABLE audit_logs DROP COLUMN actor_role;

ALTER TABLE audit_logs DROP COLUMN entity_type;

ALTER TABLE audit_logs DROP COLUMN branch_id;

ALTER TABLE audit_logs DROP COLUMN company_id;

DROP INDEX ix_notifications_deduplication_key;

DROP INDEX ix_notifications_is_archived;

DROP INDEX ix_notifications_is_read;

DROP INDEX ix_notifications_notification_type;

DROP INDEX ix_notifications_user_id;

DROP INDEX ix_notifications_priority;

DROP INDEX ix_notifications_entity_id;

DROP INDEX ix_notifications_entity_type;

DROP INDEX ix_notifications_event_type;

DROP INDEX ix_notifications_branch_id;

DROP INDEX ix_notifications_company_id;

DROP INDEX ix_notifications_actor_user_id;

ALTER TABLE notifications DROP CONSTRAINT fk_notifications_branch;

ALTER TABLE notifications DROP CONSTRAINT fk_notifications_company;

ALTER TABLE notifications DROP CONSTRAINT fk_notifications_actor_user;

ALTER TABLE notifications DROP CONSTRAINT fk_notifications_user;

ALTER TABLE notifications ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY(user_id) REFERENCES users (id);

ALTER TABLE notifications DROP CONSTRAINT notifications_related_loan_request_id_fkey;

ALTER TABLE notifications ADD CONSTRAINT notifications_related_loan_request_id_fkey FOREIGN KEY(related_loan_request_id) REFERENCES loan_requests (id);

ALTER TABLE notifications DROP CONSTRAINT notifications_related_offer_id_fkey;

ALTER TABLE notifications ADD CONSTRAINT notifications_related_offer_id_fkey FOREIGN KEY(related_offer_id) REFERENCES loan_offers (id);

ALTER TABLE notifications ALTER COLUMN notification_type DROP NOT NULL;

ALTER TABLE notifications ALTER COLUMN is_read DROP NOT NULL;

ALTER TABLE notifications DROP COLUMN archived_at;

ALTER TABLE notifications DROP COLUMN is_archived;

ALTER TABLE notifications DROP COLUMN read_at;

ALTER TABLE notifications DROP COLUMN deduplication_key;

ALTER TABLE notifications DROP COLUMN data;

ALTER TABLE notifications DROP COLUMN priority;

ALTER TABLE notifications DROP COLUMN icon;

ALTER TABLE notifications DROP COLUMN action_url;

ALTER TABLE notifications DROP COLUMN entity_id;

ALTER TABLE notifications DROP COLUMN entity_type;

ALTER TABLE notifications DROP COLUMN action;

ALTER TABLE notifications DROP COLUMN event_type;

ALTER TABLE notifications DROP COLUMN branch_id;

ALTER TABLE notifications DROP COLUMN company_id;

ALTER TABLE notifications DROP COLUMN actor_user_id;

UPDATE alembic_version SET version_num='274950a4cd45' WHERE alembic_version.version_num = '6c1f9a7e2d40';

-- Running downgrade 274950a4cd45 -> 46b05ea64319

UPDATE alembic_version SET version_num='46b05ea64319' WHERE alembic_version.version_num = '274950a4cd45';

-- Running downgrade 46b05ea64319 -> 307dcdf0187c

ALTER TABLE payment_transactions ALTER COLUMN idempotency_key TYPE VARCHAR(120);

UPDATE alembic_version SET version_num='307dcdf0187c' WHERE alembic_version.version_num = '46b05ea64319';

-- Running downgrade 307dcdf0187c -> 9f1c2d3e4a5b

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
            REFERENCES loan_companies (id);
        END
        $$;;

UPDATE alembic_version SET version_num='9f1c2d3e4a5b' WHERE alembic_version.version_num = '307dcdf0187c';

-- Running downgrade 9f1c2d3e4a5b -> 7ba90e8af6b6

DROP INDEX ix_payment_allocation_installment;

DROP INDEX ix_payment_allocation_payment;

DROP TABLE payment_allocations;

DROP INDEX ix_repayment_installment_due;

DROP INDEX ix_repayment_installment_loan;

DROP TABLE repayment_installments;

DROP INDEX ix_marketplace_unlock_request;

DROP INDEX ix_marketplace_unlock_company;

DROP TABLE marketplace_unlocks;

DROP INDEX ix_payment_provider_reference;

DROP INDEX ix_payment_idempotency;

DROP INDEX ix_payment_loan_id;

DROP INDEX ix_payment_loan_request_id;

DROP INDEX ix_payment_borrower_id;

DROP INDEX ix_payment_company_id;

DROP TABLE payment_transactions;

DROP INDEX ix_client_loan_borrower_id;

DROP INDEX ix_client_loan_branch_id;

DROP INDEX ix_client_loan_company_id;

ALTER TABLE client_company_loan DROP CONSTRAINT uq_client_loan_offer;

ALTER TABLE client_company_loan DROP CONSTRAINT uq_client_loan_request;

ALTER TABLE client_company_loan DROP CONSTRAINT fk_client_loan_disbursed_by;

ALTER TABLE client_company_loan DROP CONSTRAINT fk_client_loan_approved_by;

ALTER TABLE client_company_loan DROP CONSTRAINT fk_client_loan_branch;

ALTER TABLE client_company_loan DROP COLUMN disbursed_by_user_id;

ALTER TABLE client_company_loan DROP COLUMN approved_by_user_id;

ALTER TABLE client_company_loan DROP COLUMN approved_at;

ALTER TABLE client_company_loan DROP COLUMN processing_fee;

ALTER TABLE client_company_loan DROP COLUMN branch_id;

ALTER TABLE company_subscriptions DROP CONSTRAINT uq_company_subscription_external_reference;

DROP INDEX ix_company_subscriptions_plan_id;

DROP INDEX ix_company_subscriptions_company_id;

ALTER TABLE company_subscriptions DROP CONSTRAINT fk_company_subscription_plan;

ALTER TABLE company_subscriptions DROP COLUMN external_reference;

ALTER TABLE company_subscriptions DROP COLUMN payment_provider;

ALTER TABLE company_subscriptions DROP COLUMN auto_renew;

ALTER TABLE company_subscriptions DROP COLUMN billing_cycle;

ALTER TABLE company_subscriptions DROP COLUMN plan_id;

DROP INDEX ix_subscription_plans_code;

DROP TABLE subscription_plans;

DROP INDEX ix_loan_offers_status;

DROP INDEX ix_loan_offers_branch_id;

DROP INDEX ix_loan_offers_company_id;

DROP INDEX ix_loan_offers_request_id;

ALTER TABLE loan_offers DROP CONSTRAINT uq_loan_offer_request_company;

ALTER TABLE loan_offers DROP COLUMN accepted_at;

ALTER TABLE loan_offers DROP COLUMN expires_at;

ALTER TABLE loan_requests DROP CONSTRAINT uq_loan_requests_selected_offer;

DROP INDEX ix_loan_requests_borrower_id;

DROP INDEX ix_loan_requests_expires_at;

DROP INDEX ix_loan_requests_status;

ALTER TABLE loan_requests DROP COLUMN accepted_at;

ALTER TABLE loan_requests DROP COLUMN expires_at;

ALTER TABLE loan_requests DROP COLUMN submitted_at;

DROP INDEX ix_company_staff_user_id;

DROP INDEX ix_company_staff_branch_id;

DROP INDEX ix_loan_products_company_id;

ALTER TABLE loan_products ALTER COLUMN is_active DROP NOT NULL;

ALTER TABLE loan_products ALTER COLUMN processing_fee DROP NOT NULL;

ALTER TABLE loan_products ALTER COLUMN interest_rate_percent TYPE NUMERIC(5, 2);

ALTER TABLE loan_products ALTER COLUMN interest_rate_percent DROP NOT NULL;

DROP INDEX ix_company_staff_company_id;

DROP INDEX ix_company_branches_company_id;

ALTER TABLE company_staff DROP CONSTRAINT uq_company_staff_user_company;

ALTER TABLE company_branches DROP CONSTRAINT uq_company_branch_name;

DROP TYPE installmentstatus;

DROP TYPE unlockstatus;

DROP TYPE paymentpurpose;

DROP TYPE paymentdirection;

DROP TYPE paymentstatus;

DROP TYPE paymentprovider;

DROP TYPE billingcycle;

UPDATE alembic_version SET version_num='7ba90e8af6b6' WHERE alembic_version.version_num = '9f1c2d3e4a5b';

-- Running downgrade 7ba90e8af6b6 -> fd4aa8a11b41

ALTER TABLE borrowers ADD COLUMN marital_status maritalstatus;

ALTER TABLE borrowers ADD COLUMN middle_name VARCHAR(100);

ALTER TABLE borrowers ADD COLUMN last_name VARCHAR(100);

ALTER TABLE borrowers ADD COLUMN first_name VARCHAR(100);

ALTER TABLE borrowers ADD COLUMN town_or_village VARCHAR(150);

ALTER TABLE borrowers ADD COLUMN district VARCHAR(100);

ALTER TABLE borrowers ADD COLUMN national_id VARCHAR(50);

ALTER TABLE borrowers ADD COLUMN physical_address TEXT;

ALTER TABLE borrowers ADD COLUMN passport_number VARCHAR(50);

ALTER TABLE borrowers ADD COLUMN gender gender;

ALTER TABLE borrowers ADD COLUMN date_of_birth DATE;

ALTER TABLE borrowers ADD COLUMN nationality VARCHAR(100);

UPDATE borrowers AS borrower
            SET
                first_name = person.first_name,
                middle_name = person.middle_name,
                last_name = person.last_name,
                gender = person.gender,
                date_of_birth = person.date_of_birth,
                national_id = person.national_id,
                passport_number = person.passport_number,
                marital_status = person.marital_status,
                nationality = person.nationality,
                district = person.district,
                town_or_village = person.town_or_village,
                physical_address = person.physical_address
            FROM people AS person
            WHERE person.user_id = borrower.user_id;

DO $$
            DECLARE
                missing_count BIGINT;
            BEGIN
                SELECT COUNT(*)
                  INTO missing_count
                  FROM borrowers
                 WHERE first_name IS NULL
                    OR last_name IS NULL
                    OR gender IS NULL
                    OR date_of_birth IS NULL
                    OR district IS NULL;

                IF missing_count > 0 THEN
                    RAISE EXCEPTION
                        '% borrowers do not have complete person profiles',
                        missing_count;
                END IF;
            END
            $$;;

ALTER TABLE borrowers ALTER COLUMN first_name SET NOT NULL;

ALTER TABLE borrowers ALTER COLUMN last_name SET NOT NULL;

ALTER TABLE borrowers ALTER COLUMN gender SET NOT NULL;

ALTER TABLE borrowers ALTER COLUMN date_of_birth SET NOT NULL;

ALTER TABLE borrowers ALTER COLUMN district SET NOT NULL;

ALTER TABLE borrowers DROP CONSTRAINT fk_borrowers_user_id_users;

ALTER TABLE borrowers ADD CONSTRAINT borrowers_user_id_fkey FOREIGN KEY(user_id) REFERENCES users (id);

DROP INDEX ix_borrowers_user_id;

ALTER TABLE borrowers ADD CONSTRAINT borrowers_user_id_key UNIQUE (user_id);

ALTER TABLE borrowers ADD CONSTRAINT borrowers_passport_number_key UNIQUE (passport_number);

ALTER TABLE borrowers ADD CONSTRAINT borrowers_national_id_key UNIQUE (national_id);

ALTER TABLE users ALTER COLUMN is_verified DROP NOT NULL;

ALTER TABLE users ALTER COLUMN is_active DROP NOT NULL;

ALTER TABLE refresh_tokens ALTER COLUMN revoked DROP NOT NULL;

ALTER TABLE borrowers ALTER COLUMN consent_to_credit_checks DROP NOT NULL;

ALTER TABLE borrowers ALTER COLUMN consent_to_share_profile DROP NOT NULL;

ALTER TABLE borrowers ALTER COLUMN existing_loan_total DROP NOT NULL;

ALTER TABLE borrowers ALTER COLUMN has_existing_loans DROP NOT NULL;

DROP INDEX ix_people_passport_number;

DROP INDEX ix_people_national_id;

DROP INDEX ix_people_user_id;

DROP TABLE people;

UPDATE alembic_version SET version_num='fd4aa8a11b41' WHERE alembic_version.version_num = '7ba90e8af6b6';

-- Running downgrade fd4aa8a11b41 -> af6a1575fb01

UPDATE alembic_version SET version_num='af6a1575fb01' WHERE alembic_version.version_num = 'fd4aa8a11b41';

-- Running downgrade af6a1575fb01 -> 056d9353ae4b

ALTER TABLE client_company_loan DROP COLUMN risk_level;

ALTER TABLE client_company_loan DROP COLUMN status;

ALTER TABLE client_company_loan DROP COLUMN repayment_type;

UPDATE alembic_version SET version_num='056d9353ae4b' WHERE alembic_version.version_num = 'af6a1575fb01';

-- Running downgrade 056d9353ae4b -> cdb7c1666d74

DROP INDEX ix_client_company_loan_loan_reference;

DROP TABLE client_company_loan;

UPDATE alembic_version SET version_num='cdb7c1666d74' WHERE alembic_version.version_num = '056d9353ae4b';

-- Running downgrade cdb7c1666d74 -> a56c9061c634

CREATE TYPE repaymenttype AS ENUM ('daily', 'weekly', 'monthly', 'custom');

CREATE TYPE loanstatus AS ENUM ('pending', 'approved', 'active', 'completed', 'defaulted', 'rejected');

CREATE TYPE risklevel AS ENUM ('low', 'medium', 'high');

CREATE TABLE client_company_loan (
    company_id UUID NOT NULL, 
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
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_by VARCHAR(36), 
    loan_request_id UUID NOT NULL, 
    loan_offer_id UUID NOT NULL, 
    CONSTRAINT client_company_loan_pkey PRIMARY KEY (id), 
    CONSTRAINT client_company_loan_borrower_id_fkey FOREIGN KEY(borrower_id) REFERENCES borrowers (id), 
    CONSTRAINT client_company_loan_company_id_fkey FOREIGN KEY(company_id) REFERENCES loan_companies (id), 
    CONSTRAINT client_company_loan_loan_offer_id_fkey FOREIGN KEY(loan_offer_id) REFERENCES loan_offers (id), 
    CONSTRAINT client_company_loan_loan_request_id_fkey FOREIGN KEY(loan_request_id) REFERENCES loan_requests (id)
);

CREATE UNIQUE INDEX ix_client_company_loan_loan_reference ON client_company_loan (loan_reference);

UPDATE alembic_version SET version_num='a56c9061c634' WHERE alembic_version.version_num = 'cdb7c1666d74';

-- Running downgrade a56c9061c634 -> 80d0284b8cd6

ALTER TABLE loan_requests ADD CONSTRAINT loan_requests_selected_offer_id_fkey FOREIGN KEY(selected_offer_id) REFERENCES loan_offers (id);

ALTER TABLE loan_requests ALTER COLUMN created_at SET NOT NULL;

ALTER TABLE loan_offers ALTER COLUMN created_at SET NOT NULL;

ALTER TABLE client_company_loan DROP CONSTRAINT client_company_loan_loan_offer_id_fkey;

ALTER TABLE client_company_loan DROP CONSTRAINT client_company_loan_loan_request_id_fkey;

ALTER TABLE client_company_loan ALTER COLUMN created_at SET NOT NULL;

ALTER TABLE client_company_loan ALTER COLUMN company_id DROP NOT NULL;

ALTER TABLE client_company_loan DROP COLUMN loan_offer_id;

ALTER TABLE client_company_loan DROP COLUMN loan_request_id;

UPDATE alembic_version SET version_num='80d0284b8cd6' WHERE alembic_version.version_num = 'a56c9061c634';

-- Running downgrade 80d0284b8cd6 -> 44822a754848

DROP INDEX ix_client_company_loan_loan_reference;

DROP TABLE client_company_loan;

UPDATE alembic_version SET version_num='44822a754848' WHERE alembic_version.version_num = '80d0284b8cd6';

-- Running downgrade 44822a754848 -> d16e137105d7

DROP INDEX ix_refresh_tokens_jti;

DROP TABLE refresh_tokens;

UPDATE alembic_version SET version_num='d16e137105d7' WHERE alembic_version.version_num = '44822a754848';

-- Running downgrade d16e137105d7 -> 48e0a5d6cb1f

DROP TABLE broadcast;

UPDATE alembic_version SET version_num='48e0a5d6cb1f' WHERE alembic_version.version_num = 'd16e137105d7';

-- Running downgrade 48e0a5d6cb1f -> b0c4c142919a

DROP TABLE audit_logs;

UPDATE alembic_version SET version_num='b0c4c142919a' WHERE alembic_version.version_num = '48e0a5d6cb1f';

-- Running downgrade b0c4c142919a -> 77031f1f0be4

DROP TABLE company_subscriptions;

UPDATE alembic_version SET version_num='77031f1f0be4' WHERE alembic_version.version_num = 'b0c4c142919a';

-- Running downgrade 77031f1f0be4 -> db8c1b7032c2

DROP TABLE notifications;

UPDATE alembic_version SET version_num='db8c1b7032c2' WHERE alembic_version.version_num = '77031f1f0be4';

-- Running downgrade db8c1b7032c2 -> 920a67b52323

ALTER TABLE loan_requests DROP CONSTRAINT loan_requests_selected_offer_id_fkey;

ALTER TABLE loan_requests DROP COLUMN selected_offer_id;

UPDATE alembic_version SET version_num='920a67b52323' WHERE alembic_version.version_num = 'db8c1b7032c2';

-- Running downgrade 920a67b52323 -> 464f4729f8a7

DROP TABLE loan_offers;

UPDATE alembic_version SET version_num='464f4729f8a7' WHERE alembic_version.version_num = '920a67b52323';

-- Running downgrade 464f4729f8a7 -> 8563cd58deb9

DROP TABLE lender_access_requests;

UPDATE alembic_version SET version_num='8563cd58deb9' WHERE alembic_version.version_num = '464f4729f8a7';

-- Running downgrade 8563cd58deb9 -> d09fde6cd60e

DROP TABLE loan_request_documents;

DROP TABLE borrower_documents;

UPDATE alembic_version SET version_num='d09fde6cd60e' WHERE alembic_version.version_num = '8563cd58deb9';

-- Running downgrade d09fde6cd60e -> 15c00a058229

DROP TABLE loan_requests;

UPDATE alembic_version SET version_num='15c00a058229' WHERE alembic_version.version_num = 'd09fde6cd60e';

-- Running downgrade 15c00a058229 -> 790ed6fd651d

DROP TABLE loan_products;

UPDATE alembic_version SET version_num='790ed6fd651d' WHERE alembic_version.version_num = '15c00a058229';

-- Running downgrade 790ed6fd651d -> 96e6e94f2ba7

ALTER TABLE company_staff DROP COLUMN role;

UPDATE alembic_version SET version_num='96e6e94f2ba7' WHERE alembic_version.version_num = '790ed6fd651d';

-- Running downgrade 96e6e94f2ba7 -> f86a6ab5a269

DROP TABLE company_staff;

UPDATE alembic_version SET version_num='f86a6ab5a269' WHERE alembic_version.version_num = '96e6e94f2ba7';

-- Running downgrade f86a6ab5a269 -> b0a8b024a79e

DROP TABLE company_branches;

UPDATE alembic_version SET version_num='b0a8b024a79e' WHERE alembic_version.version_num = 'f86a6ab5a269';

-- Running downgrade b0a8b024a79e -> 4ffb06dcde89

DROP TABLE loan_companies;

UPDATE alembic_version SET version_num='4ffb06dcde89' WHERE alembic_version.version_num = 'b0a8b024a79e';

-- Running downgrade 4ffb06dcde89 -> 3057a2cdb0ea

DROP TABLE borrowers;

UPDATE alembic_version SET version_num='3057a2cdb0ea' WHERE alembic_version.version_num = '4ffb06dcde89';

-- Running downgrade 3057a2cdb0ea -> 

DROP INDEX ix_users_phone;

DROP INDEX ix_users_email;

DROP TABLE users;

DELETE FROM alembic_version WHERE alembic_version.version_num = '3057a2cdb0ea';

DROP TABLE alembic_version;

COMMIT;

