# LoanHub Frontend Typecheck Fixes

Fixed the 16 reported TypeScript errors:

1. Preserved the non-null marketplace request ID before async handlers.
2. Updated `LoadingPanel` usage from `title` to `label`.
3. Removed unsupported `title` from `ErrorPanel`.
4. Restored missing `LoanCompany` and Lucide imports in the pending-company card.
5. Allowed nullable branch values in `DetailCard`.
6. Removed stale `admins` prop usage; `CompanyAdminTable` now owns its AppData filtering.
7. Closed `socketRef.current` during notification-provider cleanup.

Run locally:

```bash
pnpm typecheck
pnpm lint
pnpm build
```
