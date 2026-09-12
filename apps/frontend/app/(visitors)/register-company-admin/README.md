# LoanHub Modular Company Registration

Copy the `_components`, `_hooks`, `_lib`, and `_types` folders beside your registration `page.tsx`.

Expected route example:

```text
app/(auth)/register/company-owner/
├── page.tsx
├── _components/
├── _hooks/
├── _lib/
└── _types/
```

The implementation expects these existing imports:

```ts
import { registerCompanyOwner } from "@/api/companyRegistration";
import { getErrorMessage } from "@/utils/apiError";
```

It uses Tailwind CSS, Lucide React, Sonner, and the Next.js App Router.
