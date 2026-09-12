# Frontend Code Map
## Main layers
- `app/`: route groups and pages.
- `components/`: reusable UI and business workspaces.
- `provider/`: authentication, tenant, realtime, notifications, chat and app-data contexts.
- `store/`: Redux slices, hooks and async operations.
- `api/`: typed REST clients.
- `types/`: shared TypeScript contracts.
- `lib/` and `utils/`: storage, role routing, API client, formatting and safe toasts.
## /borrower
- `/borrower/chat` - `(dashboard)/borrower/chat/page.tsx`
- `/borrower/files` - `(dashboard)/borrower/files/page.tsx`
- `/borrower/loans` - `(dashboard)/borrower/loans/page.tsx`
- `/borrower/notifications` - `(dashboard)/borrower/notifications/page.tsx`
- `/borrower` - `(dashboard)/borrower/page.tsx`
- `/borrower/payments` - `(dashboard)/borrower/payments/page.tsx`
- `/borrower/profile` - `(dashboard)/borrower/profile/page.tsx`
- `/borrower/requests` - `(dashboard)/borrower/requests/page.tsx`
## /borrower-registration
- `/borrower-registration` - `(visitors)/borrower-registration/page.tsx`
## /choose-account-type
- `/choose-account-type` - `(visitors)/choose-account-type/page.tsx`
## /company
- `/company/accounting` - `(dashboard)/company/accounting/page.tsx`
- `/company/activity` - `(dashboard)/company/activity/page.tsx`
- `/company/billing` - `(dashboard)/company/billing/page.tsx`
- `/company/branches` - `(dashboard)/company/branches/page.tsx`
- `/company/chat` - `(dashboard)/company/chat/page.tsx`
- `/company/employees` - `(dashboard)/company/employees/page.tsx`
- `/company/files` - `(dashboard)/company/files/page.tsx`
- `/company/loans` - `(dashboard)/company/loans/page.tsx`
- `/company/marketplace` - `(dashboard)/company/marketplace/page.tsx`
- `/company/notifications` - `(dashboard)/company/notifications/page.tsx`
- `/company` - `(dashboard)/company/page.tsx`
- `/company/payments` - `(dashboard)/company/payments/page.tsx`
- `/company/performance` - `(dashboard)/company/performance/page.tsx`
- `/company/products` - `(dashboard)/company/products/page.tsx`
- `/company/reports` - `(dashboard)/company/reports/page.tsx`
- `/company/settings` - `(dashboard)/company/settings/page.tsx`
- `/company/staff` - `(dashboard)/company/staff/page.tsx`
## /company-admin
- `/company-admin` - `(dashboard)/company-admin/page.tsx`
## /forgot-password
- `/forgot-password` - `(auth)/forgot-password/page.tsx`
## /greetings
- `/greetings` - `(visitors)/greetings/page.tsx`
## /lender-access
- `/lender-access` - `(visitors)/lender-access/page.tsx`
## /login
- `/login` - `(auth)/login/page.tsx`
## /public
- `/` - `page.tsx`
## /register-company-admin
- `/register-company-admin` - `(visitors)/register-company-admin/page.tsx`
## /superadmin
- `/superadmin/accounting` - `(dashboard)/superadmin/accounting/page.tsx`
- `/superadmin/activity` - `(dashboard)/superadmin/activity/page.tsx`
- `/superadmin/chat` - `(dashboard)/superadmin/chat/page.tsx`
- `/superadmin/companies/[id]` - `(dashboard)/superadmin/companies/[id]/page.tsx`
- `/superadmin/companies/branches` - `(dashboard)/superadmin/companies/branches/page.tsx`
- `/superadmin/companies` - `(dashboard)/superadmin/companies/page.tsx`
- `/superadmin/company-admins` - `(dashboard)/superadmin/company-admins/page.tsx`
- `/superadmin/files` - `(dashboard)/superadmin/files/page.tsx`
- `/superadmin/loans/[id]` - `(dashboard)/superadmin/loans/[id]/page.tsx`
- `/superadmin/loans` - `(dashboard)/superadmin/loans/page.tsx`
- `/superadmin/notifications` - `(dashboard)/superadmin/notifications/page.tsx`
- `/superadmin` - `(dashboard)/superadmin/page.tsx`
- `/superadmin/payments` - `(dashboard)/superadmin/payments/page.tsx`
- `/superadmin/performance` - `(dashboard)/superadmin/performance/page.tsx`
- `/superadmin/plans` - `(dashboard)/superadmin/plans/page.tsx`
- `/superadmin/reports` - `(dashboard)/superadmin/reports/page.tsx`
- `/superadmin/system-errors` - `(dashboard)/superadmin/system-errors/page.tsx`
## Where to change common frontend behaviour

| Change | Primary files |
|---|---|
| Login/session refresh | `api/auth.ts`, `lib/api.ts`, auth provider and auth Redux slice |
| Active company selection | tenant provider, storage helpers and Axios `X-Company-ID` interceptor |
| Realtime chat/notifications | `provider/realtimeProvider.tsx`, notification and chat providers |
| Role navigation | role shells, navigation configuration and `lib/role-redirect.ts` |
| Theme | `theme-provider.tsx`, `theme-switcher.tsx`, `app/globals.css` |
| Safe API messages | `utils/apiError.ts`, `utils/toast.ts` |
| Page-specific workflows | matching `app/.../page.tsx`, `components/...` and `api/...` files |
