"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { createLoanProduct, updateLoanProduct } from "@/api/loanProducts";
import { Checkbox } from "@/components/ui/checkbox";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { INTEREST_METHOD_OPTIONS, interestMethodOption } from "@/lib/interest-methods";
import type { InterestMethod } from "@/types/loan";
import type { LoanProduct, LoanProductCreatePayload } from "@/types/loanProduct";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

export const EMPTY_LOAN_PRODUCT: LoanProductCreatePayload = {
  name: "",
  description: "",
  min_amount: 500,
  max_amount: 10_000,
  min_term_months: 1,
  max_term_months: 12,
  interest_method: "micro_loan",
  interest_rate_percent: 20,
  processing_fee: 0,
  is_active: true,
};

type LoanProductDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  product?: LoanProduct | null;
  onSaved?: (product: LoanProduct) => void | Promise<void>;
};

function formFromProduct(product?: LoanProduct | null): LoanProductCreatePayload {
  if (!product) return { ...EMPTY_LOAN_PRODUCT };
  return {
    name: product.name,
    description: product.description ?? "",
    min_amount: Number(product.min_amount),
    max_amount: Number(product.max_amount),
    min_term_months: product.min_term_months,
    max_term_months: product.max_term_months,
    interest_method: product.interest_method ?? "micro_loan",
    interest_rate_percent: Number(product.interest_rate_percent),
    processing_fee: Number(product.processing_fee),
    is_active: product.is_active,
  };
}

export function LoanProductDialog({
  open,
  onOpenChange,
  product,
  onSaved,
}: LoanProductDialogProps) {
  const [form, setForm] = useState<LoanProductCreatePayload>(() => formFromProduct(product));
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    const timer = window.setTimeout(() => setForm(formFromProduct(product)), 0);
    return () => window.clearTimeout(timer);
  }, [open, product]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (form.max_amount < form.min_amount) {
      toast.error("Maximum amount cannot be below minimum amount");
      return;
    }
    if (form.max_term_months < form.min_term_months) {
      toast.error("Maximum term cannot be below minimum term");
      return;
    }

    setSubmitting(true);
    try {
      const saved = product
        ? await updateLoanProduct(product.id, form)
        : await createLoanProduct(form);
      await onSaved?.(saved);
      toast.success(product ? "Loan product updated" : "Loan product created");
      onOpenChange(false);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Loan product could not be saved"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <CustomDialog
      open={open}
      onOpenChange={(next) => !submitting && onOpenChange(next)}
      title={product ? "Edit loan product" : "Create loan product"}
      description="Set the amount range, term, interest method, rate and processing fee used by every calculator, offer, schedule and contract."
      contentClassName="sm:max-w-3xl"
    >
      <form onSubmit={submit} className="space-y-6 p-6 sm:p-8">
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Product name" className="sm:col-span-2">
            <Input
              required
              minLength={2}
              maxLength={150}
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="Example: Six-month reducing balance loan"
            />
          </Field>
          <Field label="Description" className="sm:col-span-2">
            <Textarea
              rows={3}
              value={form.description ?? ""}
              onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
              placeholder="Explain who qualifies and how this product is normally used."
            />
          </Field>
          <NumberField label="Minimum amount" value={form.min_amount} min={0.01} onChange={(value) => setForm((current) => ({ ...current, min_amount: value }))} />
          <NumberField label="Maximum amount" value={form.max_amount} min={0.01} onChange={(value) => setForm((current) => ({ ...current, max_amount: value }))} />
          <NumberField label="Minimum term (months)" value={form.min_term_months} min={1} max={120} step={1} onChange={(value) => setForm((current) => ({ ...current, min_term_months: value }))} />
          <NumberField label="Maximum term (months)" value={form.max_term_months} min={1} max={120} step={1} onChange={(value) => setForm((current) => ({ ...current, max_term_months: value }))} />
          <Field label="Interest method" className="sm:col-span-2">
            <Select
              value={form.interest_method ?? "micro_loan"}
              onValueChange={(value) => setForm((current) => ({ ...current, interest_method: value as InterestMethod }))}
            >
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{INTEREST_METHOD_OPTIONS.map((method) => <SelectItem key={method.value} value={method.value}>{method.label}</SelectItem>)}</SelectContent>
            </Select>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">{interestMethodOption(form.interest_method ?? "micro_loan").description}</p>
          </Field>
          <NumberField label={interestMethodOption(form.interest_method ?? "micro_loan").rateLabel} value={form.interest_rate_percent ?? 0} min={0} max={100} step={0.001} onChange={(value) => setForm((current) => ({ ...current, interest_rate_percent: value }))} />
          <NumberField label="Processing fee" value={form.processing_fee ?? 0} min={0} onChange={(value) => setForm((current) => ({ ...current, processing_fee: value }))} />
        </div>

        <label className="flex cursor-pointer items-start gap-3 rounded-2xl border bg-muted/25 p-4">
          <Checkbox
            checked={form.is_active ?? true}
            onCheckedChange={(checked) => setForm((current) => ({ ...current, is_active: checked === true }))}
          />
          <span>
            <strong className="block text-sm">Active product</strong>
            <span className="text-xs leading-5 text-muted-foreground">Make the product available immediately in internal application and approval forms.</span>
          </span>
        </label>

        <DialogFooter className="mx-0 mb-0">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>Cancel</Button>
          <LoadingButton type="submit" loading={submitting} loadingText={product ? "Saving changes…" : "Creating product…"}>
            {product ? "Save changes" : "Create product"}
          </LoadingButton>
        </DialogFooter>
      </form>
    </CustomDialog>
  );
}

function Field({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return <div className={className}><Label className="mb-2 block">{label}</Label>{children}</div>;
}

function NumberField({
  label,
  value,
  onChange,
  min,
  max,
  step = 0.01,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max?: number;
  step?: number;
}) {
  return (
    <Field label={label}>
      <Input
        type="number"
        required
        min={min}
        max={max}
        step={step}
        value={Number.isFinite(value) ? value : ""}
        onChange={(event) => onChange(Number(event.target.value || 0))}
      />
    </Field>
  );
}
