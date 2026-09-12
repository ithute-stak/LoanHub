import Link from "next/link";
import type { ReactNode } from "react";
import { ClipboardList, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function OriginationLayout({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="outline" size="sm" asChild>
          <Link href="/company/origination">
            <ClipboardList className="h-4 w-4" />
            Origination
          </Link>
        </Button>
        <Button variant="outline" size="sm" asChild>
          <Link href="/company/origination/experian">
            <ShieldCheck className="h-4 w-4" />
            Experian credit bureau
          </Link>
        </Button>
      </div>
      {children}
    </div>
  );
}
