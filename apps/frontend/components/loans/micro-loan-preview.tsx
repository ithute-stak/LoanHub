"use client";

import { Calculator, Loader2 } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { formatMoney } from "@/lib/format";
import type { LoanCalculation } from "@/types/loan";

type MicroLoanPreviewProps = {
  calculation: LoanCalculation | null;
  calculating?: boolean;
  compact?: boolean;
};

/**
 * Backward-compatible component name. It now previews every supported
 * FastAPI interest method rather than only the legacy Micro Loan Method.
 */
export function MicroLoanPreview({
  calculation,
  calculating = false,
  compact = false,
}: MicroLoanPreviewProps) {
  if (calculating) {
    return (
      <div className="flex min-h-28 items-center justify-center gap-3 rounded-3xl border border-primary/20 bg-primary/5 text-sm font-semibold text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
        Calculating the official repayment schedule…
      </div>
    );
  }

  if (!calculation) {
    return (
      <div className="flex min-h-28 items-center justify-center gap-3 rounded-3xl border border-dashed bg-muted/25 px-5 text-center text-sm text-muted-foreground">
        <Calculator className="h-5 w-5" />
        Select a product and enter a valid amount and term to calculate automatically.
      </div>
    );
  }

  return (
    <Card className="overflow-hidden rounded-3xl border-primary/20 bg-gradient-to-br from-primary/10 via-card to-emerald-500/10 shadow-none">
      <CardContent className="p-5">
        <div className="mb-4 rounded-2xl border bg-background/70 p-4">
          <p className="text-xs font-black uppercase tracking-wider text-primary">{calculation.method_label}</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{calculation.rate_basis}</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Value label="Principal" value={formatMoney(calculation.principal)} />
          <Value label="Total interest" value={formatMoney(calculation.total_interest)} />
          <Value label="Total repayable" value={formatMoney(calculation.total_repayable)} />
          <Value label="First instalment" value={formatMoney(calculation.monthly_installment)} emphasis />
        </div>
        {!compact ? (
          <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {calculation.schedule.slice(0, 6).map((row) => (
              <div key={row.installment_number} className="rounded-2xl border bg-background/75 p-3 text-xs">
                <p className="font-black uppercase tracking-wider text-muted-foreground">Instalment {row.installment_number}</p>
                <p className="mt-1 font-bold">Total {formatMoney(row.total_due)}</p>
                <p className="mt-1 text-muted-foreground">Principal {formatMoney(row.principal_due)} · Interest {formatMoney(row.interest_due)}</p>
              </div>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Value({ label, value, emphasis = false }: { label: string; value: string; emphasis?: boolean }) {
  return (
    <div className={emphasis ? "rounded-2xl bg-primary p-4 text-primary-foreground" : "rounded-2xl bg-background/80 p-4"}>
      <p className={emphasis ? "text-[11px] font-black uppercase tracking-wider text-primary-foreground/75" : "text-[11px] font-black uppercase tracking-wider text-muted-foreground"}>{label}</p>
      <p className="mt-1 text-xl font-black">{value}</p>
    </div>
  );
}
