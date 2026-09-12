# API Catalog

The documented source exposes 146 route operations under `/api/v1`, plus root and health endpoints. The CSV contains the complete machine-readable catalog.

## accounting

| Method | Path | Function | Access hint |
|---|---|---|---|
| POST | `/accounting/bootstrap` | `bootstrap_chart` | route-specific |
| GET | `/accounting/accounts` | `list_accounts` | route-specific |
| POST | `/accounting/accounts` | `create_account` | route-specific |
| PATCH | `/accounting/accounts/{account_id}` | `update_account` | route-specific |
| GET | `/accounting/journal-entries` | `list_entries` | route-specific |
| POST | `/accounting/journal-entries` | `add_entry` | route-specific |
| POST | `/accounting/journal-entries/{entry_id}/post` | `post_entry` | route-specific |
| GET | `/accounting/trial-balance` | `trial_balance` | route-specific |
| GET | `/accounting/profit-and-loss` | `profit_and_loss` | route-specific |
| GET | `/accounting/balance-sheet` | `balance_sheet` | route-specific |

## audit

| Method | Path | Function | Access hint |
|---|---|---|---|
| GET | `/audit/events` | `list_audit_events` | authenticated, tenant context |

## auth

| Method | Path | Function | Access hint |
|---|---|---|---|
| POST | `/auth/login` | `login` | route-specific |
| POST | `/auth/websocket-session` | `create_websocket_session` | authenticated |
| POST | `/auth/password-reset-request` | `request_password_reset` | route-specific |
| GET | `/auth/me` | `me` | authenticated |
| POST | `/auth/refresh` | `refresh_token` | route-specific |
| POST | `/auth/logout` | `logout` | platform owner |
| GET | `/auth/users` | `list_users` | platform owner |
| GET | `/auth/users/{user_id}` | `get_user` | platform owner |
| PUT | `/auth/users/{user_id}` | `update_user` | platform owner |
| DELETE | `/auth/users/{user_id}` | `delete_user` | platform owner |
| GET | `/auth/impersonation-targets` | `impersonation_targets` | platform owner |
| POST | `/auth/impersonate` | `impersonate_user` | platform owner |

## billing

| Method | Path | Function | Access hint |
|---|---|---|---|
| GET | `/billing/plans` | `list_public_plans` | platform owner |
| GET | `/billing/plans/admin` | `list_all_plans_for_admin` | platform owner |
| POST | `/billing/plans` | `create_plan` | platform owner |
| PUT | `/billing/plans/{plan_id}` | `update_plan` | platform owner |
| DELETE | `/billing/plans/{plan_id}` | `delete_plan` | platform owner |
| GET | `/billing/subscriptions` | `list_subscriptions` | route-specific |
| GET | `/billing/subscriptions/current` | `current_subscription` | route-specific |
| POST | `/billing/subscriptions/checkout` | `subscription_checkout` | route-specific |
| POST | `/billing/subscriptions/{subscription_id}/cancel` | `cancel_subscription` | route-specific |

## borrower

| Method | Path | Function | Access hint |
|---|---|---|---|
| GET | `/borrowers/` | `list_borrowers` | authenticated, platform owner |
| GET | `/borrowers/me` | `get_my_borrower_profile` | authenticated, platform owner |
| GET | `/borrowers/{borrower_id}` | `get_borrower` | authenticated, platform owner |
| POST | `/borrowers/` | `create_borrower` | authenticated, platform owner |
| PUT | `/borrowers/{borrower_id}` | `update_borrower` | authenticated, platform owner |
| DELETE | `/borrowers/{borrower_id}` | `delete_borrower` | platform owner |

## borrower_registration

| Method | Path | Function | Access hint |
|---|---|---|---|
| POST | `/borrower-registration/` | `register_borrower` | route-specific |

## branches

| Method | Path | Function | Access hint |
|---|---|---|---|
| GET | `/branches/` | `list_branches` | route-specific |
| GET | `/branches/company/{company_id}` | `list_company_branches` | route-specific |
| GET | `/branches/{branch_id}` | `get_branch` | route-specific |
| POST | `/branches/` | `create_branch` | route-specific |
| PUT | `/branches/{branch_id}` | `update_branch` | route-specific |
| DELETE | `/branches/{branch_id}` | `delete_branch` | route-specific |
| PATCH | `/branches/{branch_id}/activate` | `activate_branch` | route-specific |
| PATCH | `/branches/{branch_id}/deactivate` | `deactivate_branch` | route-specific |

## chat

| Method | Path | Function | Access hint |
|---|---|---|---|
| GET | `/chat/directory` | `chat_directory` | route-specific |
| GET | `/chat/conversations` | `list_conversations` | route-specific |
| GET | `/chat/unread-count` | `unread_count` | route-specific |
| POST | `/chat/conversations` | `create_conversation` | route-specific |
| GET | `/chat/conversations/{conversation_id}/messages` | `list_messages` | route-specific |
| POST | `/chat/conversations/{conversation_id}/messages` | `send_message` | route-specific |
| POST | `/chat/conversations/{conversation_id}/files` | `send_file_message` | route-specific |
| PATCH | `/chat/conversations/{conversation_id}/read` | `mark_conversation_read` | route-specific |
| PATCH | `/chat/messages/{message_id}` | `update_message` | route-specific |
| DELETE | `/chat/messages/{message_id}` | `delete_message` | route-specific |

## company

| Method | Path | Function | Access hint |
|---|---|---|---|
| POST | `/companies/` | `create_company` | authenticated, platform owner |
| GET | `/companies/` | `list_companies` | authenticated |
| GET | `/companies/{company_id}` | `get_company` | authenticated |
| PUT | `/companies/{company_id}` | `update_company` | authenticated, platform owner |
| DELETE | `/companies/{company_id}` | `delete_company` | platform owner |
| PATCH | `/companies/{company_id}/approve` | `approve_company` | platform owner |
| PATCH | `/companies/{company_id}/reject` | `reject_company` | platform owner |
| PATCH | `/companies/{company_id}/activate` | `activate_company` | platform owner |
| PATCH | `/companies/{company_id}/deactivate` | `deactivate_company` | platform owner |
| PATCH | `/companies/{company_id}/suspend` | `suspend_company` | platform owner |

## company_registration

| Method | Path | Function | Access hint |
|---|---|---|---|
| POST | `/company-registration/` | `register_company_owner` | route-specific |

## company_staff

| Method | Path | Function | Access hint |
|---|---|---|---|
| GET | `/company-staff/` | `list_company_staff` | route-specific |
| GET | `/company-staff/{staff_id}` | `get_company_staff_member` | route-specific |
| POST | `/company-staff/` | `assign_existing_user` | route-specific |
| POST | `/company-staff/accounts` | `create_staff_account` | route-specific |
| PUT | `/company-staff/{staff_id}` | `update_company_staff` | route-specific |
| DELETE | `/company-staff/{staff_id}` | `remove_company_staff` | route-specific |

## employees

| Method | Path | Function | Access hint |
|---|---|---|---|
| GET | `/employees` | `list_employees` | route-specific |
| GET | `/employees/{staff_id}` | `get_employee` | route-specific |
| PUT | `/employees/{staff_id}/profile` | `upsert_employee_profile` | route-specific |
| GET | `/employees/{staff_id}/goals` | `list_employee_goals` | route-specific |
| POST | `/employees/{staff_id}/goals` | `create_employee_goal` | route-specific |
| PATCH | `/employees/goals/{goal_id}` | `update_goal` | route-specific |
| GET | `/employees/{staff_id}/reviews` | `list_employee_reviews` | route-specific |
| POST | `/employees/{staff_id}/reviews` | `create_employee_review` | route-specific |

## files

| Method | Path | Function | Access hint |
|---|---|---|---|
| GET | `/files` | `list_files` | route-specific |
| POST | `/files/upload` | `upload_file` | route-specific |
| GET | `/files/{file_id}` | `get_file` | route-specific |
| GET | `/files/{file_id}/download` | `download_file` | route-specific |
| DELETE | `/files/{file_id}` | `delete_file` | route-specific |

## loan_offers

| Method | Path | Function | Access hint |
|---|---|---|---|
| POST | `/loan-offers/` | `create_offer` | route-specific |
| GET | `/loan-offers/request/{loan_request_id}` | `list_offers_by_request` | authenticated, tenant context |
| GET | `/loan-offers/{offer_id}` | `get_offer` | authenticated, tenant context |
| PATCH | `/loan-offers/{offer_id}` | `update_offer` | route-specific |
| POST | `/loan-offers/{offer_id}/withdraw` | `withdraw_offer` | route-specific |
| DELETE | `/loan-offers/{offer_id}` | `delete_offer` | route-specific |

## loan_products

| Method | Path | Function | Access hint |
|---|---|---|---|
| GET | `/loan-products/public` | `list_public_products` | route-specific |
| GET | `/loan-products/` | `list_products` | route-specific |
| GET | `/loan-products/{product_id}` | `get_product` | route-specific |
| POST | `/loan-products/` | `create_product` | route-specific |
| PUT | `/loan-products/{product_id}` | `update_product` | route-specific |
| PATCH | `/loan-products/{product_id}/activate` | `activate_product` | route-specific |
| PATCH | `/loan-products/{product_id}/deactivate` | `deactivate_product` | route-specific |
| DELETE | `/loan-products/{product_id}` | `delete_product` | route-specific |

## loan_request

| Method | Path | Function | Access hint |
|---|---|---|---|
| POST | `/loan_requests/` | `create_request` | authenticated, borrower, platform owner |
| GET | `/loan_requests/` | `get_all_requests` | authenticated, borrower, platform owner |
| GET | `/loan_requests/my` | `get_my_requests` | authenticated, borrower, platform owner |
| GET | `/loan_requests/open` | `get_open_requests` | authenticated, borrower, platform owner |
| GET | `/loan_requests/{request_id}` | `get_request` | authenticated, borrower |
| PATCH | `/loan_requests/{request_id}` | `update_request` | authenticated, borrower |
| POST | `/loan_requests/{request_id}/submit` | `submit_request` | authenticated, borrower |
| POST | `/loan_requests/{request_id}/cancel` | `cancel_request` | authenticated, borrower |
| POST | `/loan_requests/{request_id}/offers/{offer_id}/accept` | `accept_request_offer` | authenticated, borrower |
| DELETE | `/loan_requests/{request_id}` | `delete_request` | authenticated, borrower |

## loans

| Method | Path | Function | Access hint |
|---|---|---|---|
| GET | `/loans/` | `list_loans` | authenticated, tenant context |
| GET | `/loans/{loan_id}` | `get_loan` | authenticated, tenant context |
| POST | `/loans/{loan_id}/disburse` | `disburse_loan` | authenticated |
| POST | `/loans/{loan_id}/repay` | `repay_loan` | authenticated |

## marketplace

| Method | Path | Function | Access hint |
|---|---|---|---|
| GET | `/marketplace/requests` | `list_marketplace_requests` | route-specific |
| GET | `/marketplace/requests/{request_id}` | `get_marketplace_request` | route-specific |
| POST | `/marketplace/requests/{request_id}/unlock` | `unlock_request` | route-specific |

## notifications

| Method | Path | Function | Access hint |
|---|---|---|---|
| GET | `/notifications` | `list_notifications` | authenticated |
| GET | `/notifications/unread-count` | `unread_count` | authenticated |
| PATCH | `/notifications/{notification_id}/read` | `mark_notification_read` | authenticated |
| PATCH | `/notifications/read-all` | `mark_all_read` | authenticated |
| PATCH | `/notifications/{notification_id}/archive` | `archive_notification` | authenticated |
| DELETE | `/notifications/{notification_id}` | `delete_notification` | authenticated |

## payments

| Method | Path | Function | Access hint |
|---|---|---|---|
| GET | `/payments/` | `list_payments` | authenticated, tenant context |
| GET | `/payments/{payment_id}` | `get_payment` | authenticated, tenant context |
| POST | `/payments/callbacks/{provider}` | `payment_callback` | route-specific |

## performance

| Method | Path | Function | Access hint |
|---|---|---|---|
| GET | `/performance/overview` | `performance_overview` | route-specific |

## person

| Method | Path | Function | Access hint |
|---|---|---|---|
| GET | `/people/` | `list_people` | authenticated, platform owner |
| GET | `/people/me` | `get_my_person` | authenticated |
| GET | `/people/user/{user_id}` | `get_person_by_user_id` | authenticated |
| GET | `/people/{person_id}` | `get_person` | authenticated |
| POST | `/people/` | `create_person` | authenticated |
| PUT | `/people/{person_id}` | `update_person` | authenticated, platform owner |
| DELETE | `/people/{person_id}` | `delete_person` | platform owner |

## reports

| Method | Path | Function | Access hint |
|---|---|---|---|
| GET | `/reports/summary` | `report_summary` | route-specific |
| GET | `/reports` | `list_reports` | route-specific |
| POST | `/reports/generate` | `generate_now` | route-specific |
| GET | `/reports/schedules` | `list_schedules` | route-specific |
| POST | `/reports/schedules` | `create_schedule` | route-specific |
| PATCH | `/reports/schedules/{schedule_id}` | `update_schedule` | route-specific |
| DELETE | `/reports/schedules/{schedule_id}` | `delete_schedule` | route-specific |

## system_errors

| Method | Path | Function | Access hint |
|---|---|---|---|
| GET | `/system-errors` | `list_system_errors` | platform owner |
| PATCH | `/system-errors/{error_id}/resolve` | `resolve_system_error` | authenticated, platform owner |
| PATCH | `/system-errors/{error_id}/reopen` | `reopen_system_error` | authenticated, platform owner |

## ws

| Method | Path | Function | Access hint |
|---|---|---|---|
| WEBSOCKET | `/ws` | `websocket_auth_endpoint` | route-specific |

