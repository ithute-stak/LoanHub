# LoanHub Modular Company Settings

Copy these files into your company settings route.

Expected structure:

```text
company/settings/
├── page.tsx
├── _components/
├── _hooks/
├── _lib/
└── _types/
```

No additional package is required. The implementation uses your existing:

- `useAppData`
- `useTenant`
- Redux `updateCompany`
- Sonner
- Lucide React
- Tailwind CSS

After copying, run:

```bash
pnpm typecheck
pnpm lint
pnpm build
```
