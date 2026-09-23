"use client";

import { useEffect, useMemo, useState } from "react";
import { BadgeCheck, Calculator, Landmark, Loader2, RefreshCw } from "lucide-react";

import { cdasOriginationApi, type CdasOriginationPreview } from "@/api/cdasOrigination";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
} from "@/components/ui/popover";
import { formatMoney } from "@/lib/format";
import type { MicroLoanCalculation } from "@/types/loan";
import type { OriginationApplication } from "@/types/origination";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type Props = {
  applicationId: string | null;
  borrowerId: string;
  calculation: MicroLoanCalculation | null;
  selectedTermCount: number;
  firstPaymentDate: string | null;
  ensureApplication: () => Promise<OriginationApplication>;
};

export function CdasLoanCollectionCard({
  applicationId,
  borrowerId,
  calculation,
  selectedTermCount,
  firstPaymentDate,
  ensureApplication,
}: Props) {
  const [enabled, setEnabled] = useState(false);
  const [open, setOpen] = useState(false);
  const [employeeNo, setEmployeeNo] = useState("");
  const [preview, setPreview] = useState<CdasOriginationPreview | null>(null);
  const [checking, setChecking] = useState(false);
  const [savingChoice, setSavingChoice] = useState(false);
  const [linkedApplicationId, setLinkedApplicationId] = useState<string | null>(applicationId);

  useEffect(() => {
    setLinkedApplicationId(applicationId);
    if (!applicationId) return;
    let cancelled = false;
    void cdasOriginationApi.getCollectionLink(applicationId)
      .then((link) => {
        if (cancelled) return;
        setEnabled(link.enabled);
        setEmployeeNo(link.employee_no ?? "");
      })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, [applicationId]);

  const readyForPreview = Boolean(
    borrowerId &&
      calculation &&
      calculation.total_repayable > 0 &&
      calculation.monthly_installment > 0 &&
      selectedTermCount > 0,
  );

  const employeeName = useMemo(() => {
    const employee = preview?.verification.employee;
    return [employee?.name, employee?.surname].filter(Boolean).join(" ");
  }, [preview]);

  async function verifyCalculateAndLink() {
    const cleaned = employeeNo.trim();
    if (!borrowerId) {
      toast.error("Select the borrower before enabling CDAS collection.");
      return;
    }
    if (!calculation || !readyForPreview) {
      toast.error("Complete the loan amount, term and repayment dates first so LoanHub can calculate the CDAS term.");
      return;
    }
    if (!cleaned) {
      toast.error("Enter the CDAS employee number.");
      return;
    }

    setChecking(true);
    try {
      const result = await cdasOriginationApi.preview(borrowerId, {
        employee_no: cleaned,
        total_repayable: calculation.total_repayable,
        planned_installment: calculation.monthly_installment,
        selected_term_count: selectedTermCount,
        first_payment_date: firstPaymentDate || null,
      });
      setPreview(result);

      // The CDAS choice belongs to one specific loan application.  If this is
      // a brand-new wizard, persist the draft first and then bind the verified
      // employee number to that draft only.
      const app = linkedApplicationId
        ? ({ id: linkedApplicationId } as OriginationApplication)
        : await ensureApplication();
      setLinkedApplicationId(app.id);
      await cdasOriginationApi.setCollectionLink(app.id, {
        enabled: true,
        employee_no: cleaned,
      });
      setEnabled(true);
      setOpen(false);
      toast.success("CDAS payroll collection linked to this loan application");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "CDAS could not verify the employee or calculate affordability."));
    } finally {
      setChecking(false);
    }
  }

  async function disableCollection() {
    setEnabled(false);
    setPreview(null);
    setOpen(false);
    if (!linkedApplicationId) return;
    setSavingChoice(true);
    try {
      await cdasOriginationApi.setCollectionLink(linkedApplicationId, { enabled: false, employee_no: null });
      setEmployeeNo("");
      toast.success("CDAS payroll collection disabled for this loan application");
    } catch (error: unknown) {
      setEnabled(true);
      toast.error(getErrorMessage(error, "The CDAS collection choice could not be updated."));
    } finally {
      setSavingChoice(false);
    }
  }

  function onCheckedChange(value: boolean | "indeterminate") {
    const checked = value === true;
    if (!checked) {
      void disableCollection();
      return;
    }
    setEnabled(true);
    setOpen(true);
  }

  return (
    <Card className="border-dashed">
      <CardContent className="space-y-4 p-4 sm:p-5">
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverAnchor asChild>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex min-w-0 items-start gap-3">
                <Checkbox
                  id="cdas-collection-enabled"
                  checked={enabled}
                  disabled={savingChoice}
                  onCheckedChange={onCheckedChange}
                  className="mt-1"
                />
                <div className="min-w-0 space-y-1">
                  <Label htmlFor="cdas-collection-enabled" className="cursor-pointer text-sm font-semibold">
                    Collect this loan through CDAS payroll deduction
                  </Label>
                  <p className="text-xs text-muted-foreground sm:text-sm">
                    Verify the Government employee number, read live affordability and calculate how quickly payroll capacity can settle this specific loan.
                  </p>
                </div>
              </div>
              {enabled && employeeNo ? (
                <Button type="button" variant="outline" size="sm" onClick={() => setOpen(true)}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Check affordability
                </Button>
              ) : null}
            </div>
          </PopoverAnchor>

          <PopoverContent align="start" className="w-[min(94vw,32rem)] p-4">
            <PopoverHeader>
              <PopoverTitle className="flex items-center gap-2">
                <Landmark className="h-4 w-4" /> CDAS payroll collection
              </PopoverTitle>
              <PopoverDescription>
                Enter the employee number. LoanHub will verify the borrower against CDAS and immediately calculate the available payroll deduction and estimated settlement term.
              </PopoverDescription>
            </PopoverHeader>

            <div className="space-y-2">
              <Label htmlFor="cdas-employee-number">CDAS employee number</Label>
              <Input
                id="cdas-employee-number"
                value={employeeNo}
                onChange={(event) => setEmployeeNo(event.target.value)}
                placeholder="Enter employee number"
                autoComplete="off"
              />
            </div>

            {!readyForPreview ? (
              <p className="rounded-md bg-muted p-3 text-xs text-muted-foreground">
                Select the borrower and complete the loan amount, term and installment dates first.
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-2 rounded-md bg-muted/50 p-3 text-xs">
                <div>
                  <span className="text-muted-foreground">Total repayable</span>
                  <p className="font-semibold">{formatMoney(calculation?.total_repayable ?? 0)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Planned installment</span>
                  <p className="font-semibold">{formatMoney(calculation?.monthly_installment ?? 0)}</p>
                </div>
              </div>
            )}

            <Button type="button" className="w-full" disabled={checking || !readyForPreview} onClick={() => void verifyCalculateAndLink()}>
              {checking ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Calculator className="mr-2 h-4 w-4" />}
              Verify employee & calculate CDAS term
            </Button>
          </PopoverContent>
        </Popover>

        {enabled && employeeNo ? (
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge variant="secondary">Employee {employeeNo}</Badge>
            {preview?.verified ? <BadgeCheck className="h-4 w-4 text-emerald-600" /> : null}
            {employeeName ? <span className="font-medium">{employeeName}</span> : null}
            {preview?.verification.employee.department ? (
              <span className="text-muted-foreground">· {preview.verification.employee.department}</span>
            ) : null}
          </div>
        ) : null}

        {enabled && preview ? (
          <div className="space-y-3 rounded-lg border bg-background p-3 sm:p-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Metric label="CDAS affordability" value={formatMoney(preview.available_affordability)} />
              <Metric label="Proposed monthly deduction" value={formatMoney(preview.proposed_monthly_deduction)} />
              <Metric
                label="Estimated payroll term"
                value={preview.estimated_installments ? `${preview.estimated_installments} month${preview.estimated_installments === 1 ? "" : "s"}` : "Waiting for capacity"}
              />
              <Metric
                label="Final deduction"
                value={preview.final_installment === null ? "—" : formatMoney(preview.final_installment)}
              />
            </div>

            <div className="flex flex-wrap gap-2">
              {preview.status === "no_capacity" ? <Badge variant="outline">Monitor for capacity</Badge> : null}
              {preview.planned_installment_covered ? <Badge variant="secondary">Planned installment covered</Badge> : null}
              {preview.within_selected_term ? <Badge variant="secondary">Within selected term</Badge> : null}
              {preview.estimated_settlement_date ? (
                <Badge variant="outline">Estimated final payroll month: {preview.estimated_settlement_date.slice(0, 7)}</Badge>
              ) : null}
            </div>

            <p className="text-xs text-muted-foreground sm:text-sm">{preview.message}</p>
            {preview.status === "no_capacity" ? (
              <p className="text-xs text-muted-foreground">
                The application can remain linked. The monthly CDAS automation will check again during the configured 14th–20th, 06:00 processing window.
              </p>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="truncate text-sm font-semibold sm:text-base">{value}</p>
    </div>
  );
}
