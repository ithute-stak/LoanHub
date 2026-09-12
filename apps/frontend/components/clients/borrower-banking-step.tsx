"use client";

import type { ReactNode } from "react";
import { CreditCard, Landmark, Plus, ShieldCheck, Trash2 } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  BANK_NAMES,
  DEFAULT_BANK_BRANCH,
  bankAccountPrefixHint,
  bankAccountValidationMessage,
  bankDetails,
} from "@/lib/banking";
import type { BankAccountInput } from "@/types/origination";

const CURRENT_YEAR = new Date().getFullYear();

function emptyBankAccount(identityName: string): BankAccountInput {
  return {
    account_holder: identityName,
    bank_name: "",
    branch_name: DEFAULT_BANK_BRANCH,
    branch_code: null,
    account_type: "savings",
    currency: "LSL",
    account_number: null,
    salary_account: false,
    verification_status: "unverified",
    verification_reference: null,
    tokenized_card_provider: null,
    tokenized_card_reference: null,
    masked_card_number: null,
    card_brand: null,
    card_expiry_month: null,
    card_expiry_year: null,
  };
}

function cardLast4(masked: string | null): string {
  return String(masked ?? "").replace(/\D/g, "").slice(-4);
}

export function BorrowerBankingStep({
  value,
  onChange,
  identityName,
}: {
  value: BankAccountInput | null;
  onChange: (value: BankAccountInput | null) => void;
  identityName: string;
}) {
  if (!value) {
    return (
      <div className="rounded-2xl border border-dashed bg-muted/10 p-6 text-center">
        <Landmark className="mx-auto h-9 w-9 text-primary" />
        <h3 className="mt-3 text-base font-black">No banking profile captured yet</h3>
        <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
          Add the borrower&apos;s bank account for affordability, salary-account verification,
          settlement and future approved payment integrations. Unbanked or cash-only borrowers
          can continue without a banking profile.
        </p>
        <Button
          type="button"
          className="mt-4"
          onClick={() => onChange(emptyBankAccount(identityName))}
        >
          <Plus className="h-4 w-4" />
          Add banking details
        </Button>
      </div>
    );
  }

  const last4 = cardLast4(value.masked_card_number);
  const accountError = bankAccountValidationMessage(value.bank_name, value.account_number);

  return (
    <div className="space-y-5">
      <Alert>
        <ShieldCheck className="h-4 w-4" />
        <AlertTitle>Protected banking information</AlertTitle>
        <AlertDescription>
          The bank account number is encrypted before storage. LoanHub does not store a full
          payment-card number, CVV/CVC security code, PIN or magnetic-stripe data. Card charging
          must use a payment-provider token; this form stores only safe card-identification metadata.
        </AlertDescription>
      </Alert>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Field label="Account holder" required>
          <Input
            className="h-11"
            value={value.account_holder}
            onChange={(event) => onChange({ ...value, account_holder: event.target.value })}
          />
        </Field>

        <Field label="Bank" required description="LoanHub supports FNB, PB, STD and NB for Lesotho banking profiles.">
          <Select
            value={value.bank_name || undefined}
            onValueChange={(bank_name) => {
              const details = bankDetails(bank_name);
              onChange({
                ...value,
                bank_name,
                branch_name: details?.branch ?? DEFAULT_BANK_BRANCH,
                branch_code: details?.code ?? null,
              });
            }}
          >
            <SelectTrigger className="h-11 w-full">
              <SelectValue placeholder="Select bank" />
            </SelectTrigger>
            <SelectContent>
              {BANK_NAMES.map((bankName) => (
                <SelectItem key={bankName} value={bankName}>{bankName}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        <Field
          label="Account number"
          required
          description={`${bankAccountPrefixHint(value.bank_name)} Encrypted at rest; review screens show only the last four characters.`}
        >
          <Input
            className="h-11"
            type="password"
            autoComplete="off"
            inputMode="numeric"
            value={value.account_number ?? ""}
            onChange={(event) => onChange({ ...value, account_number: event.target.value || null })}
            placeholder="Bank account number"
            aria-invalid={accountError ? true : undefined}
          />
          {accountError ? <p className="text-xs font-semibold text-destructive">{accountError}</p> : null}
        </Field>

        <Field label="Branch">
          <Input className="h-11" value={value.branch_name ?? DEFAULT_BANK_BRANCH} readOnly />
        </Field>

        <Field label="Bank code">
          <Input className="h-11" value={value.branch_code ?? ""} readOnly placeholder="Select a bank" />
        </Field>

        <Field label="Account type" required>
          <Select
            value={value.account_type}
            onValueChange={(account_type) => onChange({ ...value, account_type })}
          >
            <SelectTrigger className="h-11 w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="savings">Savings</SelectItem>
              <SelectItem value="current">Current / cheque</SelectItem>
              <SelectItem value="transmission">Transmission</SelectItem>
              <SelectItem value="business">Business</SelectItem>
              <SelectItem value="other">Other</SelectItem>
            </SelectContent>
          </Select>
        </Field>

        <Field label="Currency" required>
          <Select
            value={value.currency}
            onValueChange={(currency) => onChange({ ...value, currency })}
          >
            <SelectTrigger className="h-11 w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="LSL">LSL — Lesotho loti</SelectItem>
              <SelectItem value="ZAR">ZAR — South African rand</SelectItem>
              <SelectItem value="USD">USD — US dollar</SelectItem>
            </SelectContent>
          </Select>
        </Field>

        <div className="flex items-end">
          <label className="flex min-h-11 w-full cursor-pointer items-center gap-3 rounded-xl border bg-muted/10 px-4 py-3">
            <Checkbox
              checked={value.salary_account}
              onCheckedChange={(checked) => onChange({ ...value, salary_account: checked === true })}
            />
            <span>
              <span className="block text-sm font-bold">Salary account</span>
              <span className="block text-xs text-muted-foreground">
                Borrower&apos;s salary or regular income is paid into this account.
              </span>
            </span>
          </label>
        </div>
      </div>

      <div className="rounded-2xl border bg-muted/15 p-5">
        <div className="flex items-start gap-3">
          <div className="rounded-xl bg-primary/10 p-2 text-primary">
            <CreditCard className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-black">Payment card identification (optional)</h3>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              Store only the card brand, last four digits and expiry for identification. Do not type
              the full card number or the 3/4-digit security code into LoanHub. A payment-provider
              integration should tokenize those values directly when card charging is enabled.
            </p>
          </div>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Field label="Card brand">
            <Input
              className="h-11"
              value={value.card_brand ?? ""}
              onChange={(event) => onChange({ ...value, card_brand: event.target.value || null })}
              placeholder="Visa, Mastercard..."
            />
          </Field>

          <Field label="Card last 4 digits">
            <Input
              className="h-11"
              inputMode="numeric"
              maxLength={4}
              value={last4}
              onChange={(event) => {
                const digits = event.target.value.replace(/\D/g, "").slice(0, 4);
                onChange({
                  ...value,
                  masked_card_number: digits ? `**** ${digits}` : null,
                });
              }}
              placeholder="4832"
            />
          </Field>

          <Field label="Expiry month">
            <Select
              value={value.card_expiry_month ? String(value.card_expiry_month) : "none"}
              onValueChange={(month) => onChange({
                ...value,
                card_expiry_month: month === "none" ? null : Number(month),
              })}
            >
              <SelectTrigger className="h-11 w-full"><SelectValue placeholder="Month" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Not recorded</SelectItem>
                {Array.from({ length: 12 }, (_, index) => index + 1).map((month) => (
                  <SelectItem key={month} value={String(month)}>{String(month).padStart(2, "0")}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          <Field label="Expiry year">
            <Input
              className="h-11"
              type="number"
              min={CURRENT_YEAR}
              max={2200}
              value={value.card_expiry_year ?? ""}
              onChange={(event) => onChange({
                ...value,
                card_expiry_year: event.target.value ? Number(event.target.value) : null,
              })}
              placeholder={String(CURRENT_YEAR + 3)}
            />
          </Field>
        </div>
      </div>

      <div className="flex justify-end">
        <Button type="button" variant="outline" onClick={() => onChange(null)}>
          <Trash2 className="h-4 w-4" />
          Remove banking profile
        </Button>
      </div>
    </div>
  );
}

function Field({
  label,
  required = false,
  description,
  children,
}: {
  label: string;
  required?: boolean;
  description?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-2">
      <Label className="text-sm font-bold">
        {label}
        {required ? <span className="ml-1 text-destructive">*</span> : null}
      </Label>
      {children}
      {description ? <p className="text-xs leading-5 text-muted-foreground">{description}</p> : null}
    </div>
  );
}
