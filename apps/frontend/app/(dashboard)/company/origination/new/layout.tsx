import type { ReactNode } from "react";

import { CdasLoanOptIn } from "@/components/origination/cdas-loan-opt-in";

export default function NewOriginationLayout({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-4">
      <CdasLoanOptIn />
      {children}
    </div>
  );
}
