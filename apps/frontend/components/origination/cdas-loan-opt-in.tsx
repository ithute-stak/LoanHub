"use client";

import { useEffect, useMemo, useState } from "react";
import { BadgeCheck, Calculator, CircleAlert, Loader2, WalletCards } from "lucide-react";

import { previewCdasOrigination, type CdasOriginationPreview } from "@/api/cdasOrigination";
import { listCompanyClients } from "@/api/companyClients";
import { listLoanProducts } from "@/api/loanProducts";
import { calculateLoan } from "@/api/loans";
import { originationApi } from "@/api/origination";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { formatMoney } from "@/lib/format";
import type { CompanyClient } from "@/types/companyClient";
import type { InterestMethod } from "@/types/loan";
import type { LoanProduct } from "@/types/loanProduct";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

function addMonths(anchor: Date, months: number) {
  const source = new Date(anchor);
  const day = source.getDate();
  source.setDate(1);
  source.setMonth(source.getMonth() + months);
  const monthEnd = new Date(source.getFullYear(), source.getMonth() + 1, 0).getDate();
  source.setDate(Math.min(day, monthEnd));
  return source.toISOString().slice(0, 10);
}

function fieldInput(labelText: string): HTMLInputElement | null {
  const labels = Array.from(document.querySelectorAll("label"));
  const label = labels.find((item) => (item.textContent || "").trim().toLowerCase().includes(labelText.toLowerCase()));
  return label?.parentElement?.querySelector("input") ?? null;
}

function fieldCombobox(labelText: string): HTMLElement | null {
  const labels = Array.from(document.querySelectorAll("label"));
  const label = labels.find((item) => (item.textContent || "").trim().toLowerCase().includes(labelText.toLowerCase()));
  return label?.parentElement?.querySelector('[role="combobox"]') ?? null;
}

function numberFromField(labelText: string, fallback = 0) {
  const value = Number(fieldInput(labelText)?.value ?? fallback);
  return Number.isFinite(value) ? value : fallback;
}

function resolveBorrowerFromScreen(clients: CompanyClient[]) {
  const text = (fieldCombobox("Borrower")?.textContent || "").trim();
  if (!text) return null;
  const accountReference = text.split("·").pop()?.trim();
  return clients.find((item) => item.account_reference === accountReference) ?? null;
}

function resolveProductFromScreen(products: LoanProduct[]) {
  const text = (fieldCombobox("Loan product")?.textContent || "").trim();
  if (!text) return null;
  const productName = text.split("·")[0]?.trim();
  return products.find((item) => item.name === productName) ?? null;
}

export function CdasLoanOptIn() {
  const [enabled, setEnabled] = useState(false);
  const [open, setOpen] = useState(false);
  const [employeeNo, setEmployeeNo] = useState("");
  const [checking, setChecking] = useState(false);
  const [preview, setPreview] = useState<CdasOriginationPreview | null>(null);
  const [clients, setClients] = useState<CompanyClient[]>([]);
  const [products, setProducts] = useState<LoanProduct[]>([]);

  useEffect(() => {
    void Promise.all([listCompanyClients(), listLoanProducts()])
      .then(([clientRows, productRows]) => {
        setClients(clientRows.filter((item) => item.status === "active"));
        setProducts(productRows.filter((item) => item.is_active));
      })
      .catch(() => undefined);
  }, []);

  const capacityTone = useMemo(() => {
    if (!preview) return "secondary" as const;
    if (preview.monitoring_required) return "outline" as const;
    return preview.fits_scheduled_installment ? "default" as const : "secondary" as const;
  }, [preview]);

  async function resolveLoanContext() {
    const params = new URLSearchParams(window.location.search);
    const applicationId = params.get("application");
    const borrowerParam = params.get("borrower");

    if (applicationId) {
      const workspace = await originationApi.getWorkspace(applicationId);
      const application = workspace.application;
      const product = products.find((item) => item.id === application.product_id) ?? null;
      const dueDates = application.installment_due_dates?.length
        ? application.installment_due_dates
        : Array.from({ length: application.term_count }, (_, index) => addMonths(new Date(), index + 1));
      const calculation = await calculateLoan({
        principal: Number(application.requested_amount),
        rate_percent: Number(application.interest_rate ?? product?.interest_rate_percent ?? 0),
        months: application.term_count,
        processing_fee: Number(product?.processing_fee ?? 0),
        interest_method: (product?.interest_method ?? "micro_loan") as InterestMethod,
        due_dates: dueDates,
      });
      return { borrowerId: application.borrower_id, calculation };
    }

    const borrower = borrowerParam
      ? clients.find((item) => item.borrower_id === borrowerParam) ?? null
      : resolveBorrowerFromScreen(clients);
    if (!borrower) throw new Error("Select the borrower before checking CDAS.");

    const product = resolveProductFromScreen(products);
    const principal = numberFromField("Requested amount");
    const months = Math.max(1, Math.trunc(numberFromField("Term in months", 1)));
    const rate = numberFromField("rate", Number(product?.interest_rate_percent ?? 0));
    const processingFee = numberFromField("Processing fee", Number(product?.processing_fee ?? 0));
    if (principal <= 0) throw new Error("Enter the requested loan amount before checking CDAS.");

    const visibleDates = Array.from(document.querySelectorAll<HTMLInputElement>('input[type="date"]'))
      .map((item) => item.value)
      .filter(Boolean)
      .slice(0, months);
    const dueDates = visibleDates.length === months
      ? visibleDates
      : Array.from({ length: months }, (_, index) => addMonths(new Date(), index + 1));
    const calculation = await calculateLoan({
      principal,
      rate_percent: rate,
      months,
      processing_fee: processingFee,
      interest_method: (product?.interest_method ?? "micro_loan") as InterestMethod,
      due_dates: dueDates,
    });
    return { borrowerId: borrower.borrower_id, calculation };
  }

  async function checkCdas() {
    if (!employeeNo.trim()) {
      toast.error("Enter the client's CDAS employee number.");
      return;
    }
    setChecking(true);
    setPreview(null);
    try {
      const { borrowerId, calculation } = await resolveLoanContext();
      const result = await previewCdasOrigination(borrowerId, {
        employee_no: employeeNo.trim(),
        total_repayable: Number(calculation.total_repayable),
        scheduled_installment: Number(calculation.monthly_installment),
        requested_term: Number(calculation.months),
      });
      setPreview(result);
      toast.success("CDAS employee verified and affordability loaded.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "CDAS affordability could not be checked."));
    } finally {
      setChecking(false);
    }
  }

  return (
    <div className="rounded-2xl border bg-card px-4 py-3 shadow-sm">
      <Popover open={open} onOpenChange={setOpen}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="flex cursor-pointer items-center gap-3 text-sm font-semibold">
            <Checkbox
              checked={enabled}
              onCheckedChange={(value) => {
                const next = value === true;
                setEnabled(next);
                setOpen(next);
                if (!next) setPreview(null);
              }}
            />
            <span>Collect this loan through CDAS payroll deduction</span>
          </label>
          <PopoverTrigger asChild>
            <Button type="button" variant="outline" size="sm" disabled={!enabled}>
              <WalletCards className="h-4 w-4" />
              CDAS details
            </Button>
          </PopoverTrigger>
        </div>

        <PopoverContent align="end" className="w-[min(94vw,430px)] p-4">
          <div className="space-y-4">
            <div>
              <p className="font-black">CDAS payroll collection</p>
              <p className="text-xs text-muted-foreground">
                Enter the Government payroll employee number. LoanHub verifies the employee and reads live affordability before any deduction is created.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="cdas-origination-employee-no">CDAS employee number</Label>
              <div className="flex gap-2">
                <Input
                  id="cdas-origination-employee-no"
                  value={employeeNo}
                  onChange={(event) => setEmployeeNo(event.target.value)}
                  placeholder="Employee No"
                  autoComplete="off"
                />
                <Button type="button" onClick={() => void checkCdas()} disabled={checking}>
                  {checking ? <Loader2 className="h-4 w-4 animate-spin" /> : <Calculator className="h-4 w-4" />}
                  Check
                </Button>
              </div>
            </div>

            {preview ? (
              <div className="space-y-3 rounded-xl border bg-muted/30 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="flex items-center gap-2 font-bold"><BadgeCheck className="h-4 w-4" /> Verified employee</p>
                    <p className="text-sm">{[preview.employee.name, preview.employee.surname].filter(Boolean).join(" ") || preview.employee_no}</p>
                    {preview.employee.department ? <p className="text-xs text-muted-foreground">{preview.employee.department}</p> : null}
                  </div>
                  <Badge variant={capacityTone}>{preview.monitoring_required ? "Monitor" : preview.fits_scheduled_installment ? "Fits" : "Term extends"}</Badge>
                </div>

                <div className="grid grid-cols-2 gap-2 text-sm">
                  <Metric label="CDAS affordability" value={formatMoney(preview.affordability)} />
                  <Metric label="Loan installment" value={formatMoney(preview.scheduled_installment)} />
                  <Metric label="Total repayable" value={formatMoney(preview.total_repayable)} />
                  <Metric label="Remaining capacity" value={formatMoney(preview.remaining_affordability_after_scheduled)} />
                  <Metric label="Requested term" value={`${preview.requested_term} months`} />
                  <Metric label="Estimated CDAS term" value={preview.estimated_installments_at_effective_deduction ? `${preview.estimated_installments_at_effective_deduction} months` : "Waiting for capacity"} />
                  <Metric label="Estimated settlement" value={preview.estimated_settlement_month ?? "—"} />
                  <Metric label="Fastest at full capacity" value={preview.fastest_installments_at_full_affordability ? `${preview.fastest_installments_at_full_affordability} months` : "—"} />
                </div>

                {!preview.fits_scheduled_installment && preview.affordability > 0 ? (
                  <div className="flex gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2 text-xs">
                    <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>The planned installment is {formatMoney(preview.payroll_shortfall)} above current CDAS affordability. The preview shows the longer settlement period at the capacity currently available.</span>
                  </div>
                ) : null}
                {preview.monitoring_required ? (
                  <p className="text-xs text-muted-foreground">No capacity is available now. The verified employee number is retained so the existing monthly CDAS automation can detect future affordability.</p>
                ) : null}
              </div>
            ) : null}
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-background p-2">
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className="font-bold">{value}</p>
    </div>
  );
}
