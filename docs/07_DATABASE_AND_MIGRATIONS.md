# Database Models and Migrations

Latest head: `f1a9c4e7b620`. The chain contains 34 ordered revisions. Never delete an applied revision or use `alembic stamp head` to hide missing history.

## Model catalog

### `accounting_accounts` - `AccountingAccount`
Defined in `database/models/accounting.py`. Columns: scope_key, scope_type, company_id, branch_id, parent_id, code, name, account_type, normal_balance, description, is_system, is_active.
Foreign keys: `company_id` -> `loan_companies.id`, `branch_id` -> `company_branches.id`, `parent_id` -> `accounting_accounts.id`.

### `audit_logs` - `AuditLog`
Defined in `database/models/audit_log.py`. Columns: user_id, company_id, branch_id, action, table_name, entity_type, record_id, description, actor_role, severity, status, before_data, after_data, changed_fields, event_data, request_id, ip_address, user_agent, duration_ms.
Foreign keys: `user_id` -> `users.id`, `company_id` -> `loan_companies.id`, `branch_id` -> `company_branches.id`.

### `borrower_documents` - `BorrowerDocument`
Defined in `database/models/documents.py`. Columns: borrower_id, document_type, file_name, file_url, is_verified.
Foreign keys: `borrower_id` -> `borrowers.id`.

### `borrowers` - `Borrower`
Defined in `database/models/borrower.py`. Columns: user_id, employment_status, employer_name, job_title, monthly_income, salary_date, has_existing_loans, existing_loan_total, consent_to_share_profile, consent_to_credit_checks.
Foreign keys: `user_id` -> `users.id`.

### `broadcast` - `Broadcast`
Defined in `database/models/notificat.py`. Columns: user_id, channel, title, message, event_type, entity, entity_id, data, is_read.
Foreign keys: `user_id` -> `users.id`.

### `chat_conversations` - `ChatConversation`
Defined in `database/models/chat.py`. Columns: reference, company_id, branch_id, created_by_user_id, title, conversation_type, context_type, context_id, is_group, is_archived, last_message_at.
Foreign keys: `company_id` -> `loan_companies.id`, `branch_id` -> `company_branches.id`, `created_by_user_id` -> `users.id`.

### `chat_message_attachments` - `ChatMessageAttachment`
Defined in `database/models/chat.py`. Columns: message_id, file_id, caption.
Foreign keys: `message_id` -> `chat_messages.id`, `file_id` -> `managed_files.id`.

### `chat_messages` - `ChatMessage`
Defined in `database/models/chat.py`. Columns: conversation_id, sender_user_id, company_id, branch_id, reply_to_message_id, message_type, body, body_ciphertext, body_nonce, encryption_version, client_message_id, metadata_json, edited_at, deleted_at.
Foreign keys: `conversation_id` -> `chat_conversations.id`, `sender_user_id` -> `users.id`, `company_id` -> `loan_companies.id`, `branch_id` -> `company_branches.id`, `reply_to_message_id` -> `chat_messages.id`.

### `chat_participants` - `ChatParticipant`
Defined in `database/models/chat.py`. Columns: conversation_id, user_id, participant_role, is_admin, is_active, joined_at, last_read_at, muted_until.
Foreign keys: `conversation_id` -> `chat_conversations.id`, `user_id` -> `users.id`.

### `client_company_loan` - `ClientCompanyLoan`
Defined in `database/models/client_loan_company.py`. Columns: loan_request_id, loan_offer_id, company_id, branch_id, borrower_id, loan_reference, principal_amount, interest_rate, processing_fee, total_repayable, repayment_type, repayment_period, installment_amount, approved_at, disbursed_at, first_payment_due, maturity_date, amount_paid, balance, status, risk_level, is_overdue, approved_by_user_id, disbursed_by_user_id.
Foreign keys: `loan_request_id` -> `loan_requests.id`, `loan_offer_id` -> `loan_offers.id`, `company_id` -> `loan_companies.id`, `branch_id` -> `company_branches.id`, `borrower_id` -> `borrowers.id`, `approved_by_user_id` -> `users.id`, `disbursed_by_user_id` -> `users.id`.

### `company_branches` - `CompanyBranch`
Defined in `database/models/branch.py`. Columns: company_id, name, district, town, address, phone, email, is_active.
Foreign keys: `company_id` -> `loan_companies.id`.

### `company_staff` - `CompanyStaff`
Defined in `database/models/company_staff.py`. Columns: user_id, company_id, branch_id, role, is_active.
Foreign keys: `user_id` -> `users.id`, `company_id` -> `loan_companies.id`, `branch_id` -> `company_branches.id`.

### `company_subscriptions` - `CompanySubscription`
Defined in `database/models/subscription.py`. Columns: company_id, plan_id, plan_name, amount, start_date, end_date, billing_cycle, status, auto_renew, payment_provider, external_reference.
Foreign keys: `company_id` -> `loan_companies.id`, `plan_id` -> `subscription_plans.id`.

### `employee_profiles` - `EmployeeProfile`
Defined in `database/models/employee.py`. Columns: staff_id, company_id, branch_id, reports_to_staff_id, employee_number, job_title, department, employment_type, employment_status, hire_date, probation_end_date, termination_date, base_salary, currency, skills, target_config, notes, is_manager.
Foreign keys: `staff_id` -> `company_staff.id`, `company_id` -> `loan_companies.id`, `branch_id` -> `company_branches.id`, `reports_to_staff_id` -> `company_staff.id`.

### `generated_reports` - `GeneratedReport`
Defined in `database/models/reporting.py`. Columns: reference, scope_type, company_id, branch_id, schedule_id, generated_by_user_id, file_id, title, report_type, output_format, period_start, period_end, status, metrics, error_message, generated_at.
Foreign keys: `company_id` -> `loan_companies.id`, `branch_id` -> `company_branches.id`, `schedule_id` -> `report_schedules.id`, `generated_by_user_id` -> `users.id`, `file_id` -> `managed_files.id`.

### `journal_entries` - `JournalEntry`
Defined in `database/models/accounting.py`. Columns: scope_key, scope_type, company_id, branch_id, created_by_user_id, posted_by_user_id, entry_number, entry_date, description, reference_type, reference_id, status, total_debit, total_credit, posted_at, voided_at.
Foreign keys: `company_id` -> `loan_companies.id`, `branch_id` -> `company_branches.id`, `created_by_user_id` -> `users.id`, `posted_by_user_id` -> `users.id`.

### `journal_lines` - `JournalLine`
Defined in `database/models/accounting.py`. Columns: journal_entry_id, account_id, description, debit, credit.
Foreign keys: `journal_entry_id` -> `journal_entries.id`, `account_id` -> `accounting_accounts.id`.

### `lender_access_requests` - `LenderAccessRequest`
Defined in `database/models/lender_access.py`. Columns: loan_request_id, company_id, requested_by_user_id, status, message.
Foreign keys: `loan_request_id` -> `loan_requests.id`, `company_id` -> `loan_companies.id`, `requested_by_user_id` -> `users.id`.

### `loan_companies` - `LoanCompany`
Defined in `database/models/company.py`. Columns: name, registration_number, license_number, phone, email, website, address, district, status, is_active.

### `loan_offers` - `LoanOffer`
Defined in `database/models/loan_offer.py`. Columns: loan_request_id, company_id, branch_id, offered_by_user_id, approved_amount, term_months, interest_rate_percent, processing_fee, monthly_repayment, total_repayment, notes, status, expires_at, accepted_at, created_at.
Foreign keys: `loan_request_id` -> `loan_requests.id`, `company_id` -> `loan_companies.id`, `branch_id` -> `company_branches.id`, `offered_by_user_id` -> `users.id`.

### `loan_products` - `LoanProduct`
Defined in `database/models/loan_product.py`. Columns: company_id, name, description, min_amount, max_amount, min_term_months, max_term_months, interest_rate_percent, processing_fee, is_active.
Foreign keys: `company_id` -> `loan_companies.id`.

### `loan_request_documents` - `LoanRequestDocument`
Defined in `database/models/documents.py`. Columns: loan_request_id, document_type, file_name, file_url.
Foreign keys: `loan_request_id` -> `loan_requests.id`.

### `loan_requests` - `LoanRequest`
Defined in `database/models/loan_request.py`. Columns: borrower_id, requested_amount, preferred_term_months, loan_purpose, status, visible_to_lenders, allow_lenders_to_call, selected_offer_id, submitted_at, expires_at, accepted_at, created_at.
Foreign keys: `borrower_id` -> `borrowers.id`, `selected_offer_id` -> `loan_offers.id`.

### `managed_files` - `ManagedFile`
Defined in `database/models/file_management.py`. Columns: owner_user_id, company_id, branch_id, reference, original_name, stored_name, storage_key, storage_provider, mime_type, detected_mime_type, extension, size_bytes, checksum_sha256, is_encrypted, encryption_nonce, encryption_version, scan_status, quarantined_reason, category, visibility, description, linked_entity_type, linked_entity_id, is_confidential, is_deleted, deleted_at.
Foreign keys: `owner_user_id` -> `users.id`, `company_id` -> `loan_companies.id`, `branch_id` -> `company_branches.id`.

### `marketplace_unlocks` - `MarketplaceUnlock`
Defined in `database/models/marketplace_access.py`. Columns: company_id, loan_request_id, payment_transaction_id, unlocked_by_user_id, price_paid, status, unlocked_at, expires_at.
Foreign keys: `company_id` -> `loan_companies.id`, `loan_request_id` -> `loan_requests.id`, `payment_transaction_id` -> `payment_transactions.id`, `unlocked_by_user_id` -> `users.id`.

### `notifications` - `Notification`
Defined in `database/models/notification.py`. Columns: user_id, actor_user_id, company_id, branch_id, title, message, notification_type, event_type, action, entity_type, entity_id, action_url, icon, priority, data, deduplication_key, is_read, read_at, is_archived, archived_at, related_loan_request_id, related_offer_id.
Foreign keys: `user_id` -> `users.id`, `actor_user_id` -> `users.id`, `company_id` -> `loan_companies.id`, `branch_id` -> `company_branches.id`, `related_loan_request_id` -> `loan_requests.id`, `related_offer_id` -> `loan_offers.id`.

### `payment_allocations` - `PaymentAllocation`
Defined in `database/models/repayment.py`. Columns: payment_id, installment_id, amount.
Foreign keys: `payment_id` -> `payment_transactions.id`, `installment_id` -> `repayment_installments.id`.

### `payment_transactions` - `PaymentTransaction`
Defined in `database/models/payment.py`. Columns: company_id, borrower_id, loan_request_id, loan_id, initiated_by_user_id, provider, direction, purpose, status, amount, currency, payer_phone, payee_phone, idempotency_key, provider_reference, provider_payload, failure_reason, completed_at.
Foreign keys: `company_id` -> `loan_companies.id`, `borrower_id` -> `borrowers.id`, `loan_request_id` -> `loan_requests.id`, `loan_id` -> `client_company_loan.id`, `initiated_by_user_id` -> `users.id`.

### `people` - `Person`
Defined in `database/models/person.py`. Columns: user_id, first_name, middle_name, last_name, gender, date_of_birth, national_id, passport_number, marital_status, nationality, district, town_or_village, physical_address.
Foreign keys: `user_id` -> `users.id`.

### `performance_goals` - `PerformanceGoal`
Defined in `database/models/employee.py`. Columns: employee_id, company_id, branch_id, created_by_user_id, title, description, category, target_value, current_value, unit, weight, period_start, period_end, status, completed_at.
Foreign keys: `employee_id` -> `employee_profiles.id`, `company_id` -> `loan_companies.id`, `branch_id` -> `company_branches.id`, `created_by_user_id` -> `users.id`.

### `performance_reviews` - `PerformanceReview`
Defined in `database/models/employee.py`. Columns: employee_id, reviewer_staff_id, company_id, branch_id, period_start, period_end, overall_score, rating, status, strengths, improvements, comments, metrics, employee_acknowledged_at.
Foreign keys: `employee_id` -> `employee_profiles.id`, `reviewer_staff_id` -> `company_staff.id`, `company_id` -> `loan_companies.id`, `branch_id` -> `company_branches.id`.

### `refresh_tokens` - `RefreshToken`
Defined in `database/models/user.py`. Columns: jti, user_id, revoked, expires_at.
Foreign keys: `user_id` -> `users.id`.

### `repayment_installments` - `RepaymentInstallment`
Defined in `database/models/repayment.py`. Columns: loan_id, installment_number, due_date, principal_due, interest_due, fee_due, total_due, paid_amount, status, paid_at.
Foreign keys: `loan_id` -> `client_company_loan.id`.

### `report_schedules` - `ReportSchedule`
Defined in `database/models/reporting.py`. Columns: scope_type, company_id, branch_id, created_by_user_id, name, report_type, frequency, output_format, recipients, is_active, next_run_at, last_run_at, last_status, last_error.
Foreign keys: `company_id` -> `loan_companies.id`, `branch_id` -> `company_branches.id`, `created_by_user_id` -> `users.id`.

### `subscription_plans` - `SubscriptionPlan`
Defined in `database/models/subscription.py`. Columns: code, name, description, monthly_price, annual_price, marketplace_unlock_fee, transaction_fee_percent, features, limits, is_active, is_public.

### `system_error_logs` - `SystemErrorLog`
Defined in `database/models/system_error.py`. Columns: request_id, fingerprint, user_id, company_id, branch_id, method, path, status_code, error_type, message, stack_trace, severity, environment, user_agent, context, occurrence_count, first_seen_at, last_seen_at, is_resolved, resolved_at, resolved_by_user_id, resolution_notes.
Foreign keys: `user_id` -> `users.id`, `company_id` -> `loan_companies.id`, `branch_id` -> `company_branches.id`, `resolved_by_user_id` -> `users.id`.

### `users` - `User`
Defined in `database/models/user.py`. Columns: email, phone, password_hash, role, is_active, is_verified, last_seen_at.

## Migration order

1. `3057a2cdb0ea` - initial loan marketplace schema
2. `4ffb06dcde89` - initial loan marketplace schema
3. `b0a8b024a79e` - initial loan marketplace schema
4. `f86a6ab5a269` - initial loan marketplace schema
5. `96e6e94f2ba7` - c
6. `790ed6fd651d` - c
7. `15c00a058229` - c
8. `d09fde6cd60e` - c
9. `8563cd58deb9` - c
10. `464f4729f8a7` - c
11. `920a67b52323` - c
12. `db8c1b7032c2` - c
13. `77031f1f0be4` - c
14. `b0c4c142919a` - c
15. `48e0a5d6cb1f` - c
16. `d16e137105d7` - add school admin
17. `44822a754848` - add school admin
18. `80d0284b8cd6` - add loan company client
19. `a56c9061c634` - add loan company client
20. `cdb7c1666d74` - add loan company client
21. `056d9353ae4b` - add loan company client
22. `af6a1575fb01` - add loan company client
23. `fd4aa8a11b41` - add person profiles
24. `7ba90e8af6b6` - add people model
25. `9f1c2d3e4a5b` - multitenant SaaS, billing, payments and repayment foundation
26. `307dcdf0187c` - normalize company staff company cascade
27. `46b05ea64319` - expand payment idempotency key
28. `274950a4cd45` - legacy migration-chain compatibility marker
29. `6c1f9a7e2d40` - realtime transparency, employees, performance and system errors
30. `3957062b7c66` - compatibility marker for an already-recorded local revision
31. `8d2f4a1b7c90` - marketable chat, files, reports and accounting
32. `b84d1f2a9c30` - canonical schema repair after compatibility and marketable revisions
33. `d4e7b6c1a930` - align legacy index names and restore the selected-offer foreign key
34. `f1a9c4e7b620` - final security, presence and encrypted content alignment
