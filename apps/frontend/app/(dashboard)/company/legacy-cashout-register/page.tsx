import Link from "next/link";
import { BookOpenCheck } from "lucide-react";

import { LegacyCashoutRegister } from "@/components/legacy-cashout/legacy-cashout-register";
import { Button } from "@/components/ui/button";

export default function LegacyCashoutRegisterPage() {
  return (
    <div className="w-full space-y-3 px-2 sm:px-3 lg:px-4">
      <div className="flex justify-end">
        <Button asChild className="rounded-xl">
          <Link href="/company/folio-book">
            <BookOpenCheck className="h-4 w-4" />
            Open permanent Loan Folio Book
          </Link>
        </Button>
      </div>
      <div className="[&>div]:mx-0 [&>div]:w-full [&>div]:max-w-none">
        <LegacyCashoutRegister />
      </div>
    </div>
  );
}
