"use client";

import { Landmark, Plus, ShieldCheck, Trash2 } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import {
  BANK_NAMES,
  DEFAULT_BANK_BRANCH,
  bankAccountPrefixHint,
  bankAccountValidationMessage,
  bankDetails,
  isBankName,
} from "@/lib/banking";
import { titleCase } from "@/lib/format";
import type { BankAccountInput } from "@/types/origination";

interface BankAccountsStepProps {
  values: BankAccountInput[];
  onChange: (value: BankAccountInput[]) => void;
  identityName: string;
  allowVerification?: boolean;
  allowTokenizedCard?: boolean;
  ownerLabel?: string;
}

function emptyBankAccount(identityName: string): BankAccountInput {
  return {
    id: null,
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

export function BankAccountsStep({
  values,
  onChange,
  identityName,
  allowVerification = false,
  allowTokenizedCard = false,
  ownerLabel = "Borrower",
}: BankAccountsStepProps) {
  const update = (index: number, patch: Partial<BankAccountInput>) => {
    onChange(values.map((row, rowIndex) => {
      if (patch.salary_account && rowIndex !== index) {
        return { ...row, salary_account: false };
      }
      return rowIndex === index ? { ...row, ...patch } : row;
    }));
  };

  const addAccount = () => {
    onChange([...values, emptyBankAccount(identityName)]);
  };

  return (
    <div className="space-y-6">
      <Alert>
        <ShieldCheck className="h-4 w-4" />
        <AlertTitle>LoanHub banking standard</AlertTitle>
        <AlertDescription>
          New and edited banking details use FNB, PB, STD or NB. Maseru Central is the standard
          branch and the bank code is filled automatically. Full account numbers remain encrypted.
        </AlertDescription>
      </Alert>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="font-black">{ownerLabel} bank accounts</h3>
          <p className="text-sm text-muted-foreground">
            Multiple accounts are supported. Only one account can be marked as the salary account.
          </p>
        </div>
        <Button type="button" variant="outline" onClick={addAccount}>
          <Plus className="h-4 w-4" />Add another account
        </Button>
      </div>

      {!values.length ? (
        <div className="rounded-3xl border border-dashed p-10 text-center">
          <Landmark className="mx-auto h-10 w-10 text-primary" />
          <h3 className="mt-3 font-black">No bank accounts captured</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Add a bank account when banking details are available.
          </p>
          <Button type="button" className="mt-5" onClick={addAccount}>
            <Plus className="h-4 w-4" />Add bank account
          </Button>
        </div>
      ) : null}

      {values.map((item, index) => {
        const details = bankDetails(item.bank_name);
        const legacyBank = item.bank_name && !isBankName(item.bank_name) ? item.bank_name : null;
        const branchValue = details?.branch ?? item.branch_name ?? DEFAULT_BANK_BRANCH;
        const codeValue = details?.code ?? item.branch_code ?? "";
        const accountError = item.id && !item.account_number
          ? null
          : bankAccountValidationMessage(item.bank_name, item.account_number);

        return (
          <section key={item.id ?? `bank-${index}`} className="space-y-5 rounded-3xl border bg-muted/10 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-black uppercase tracking-wider text-primary">Account {index + 1}</p>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <p className="text-sm text-muted-foreground">
                    {item.id ? "Existing protected account" : "New account"}
                  </p>
                  {item.verification_status ? (
                    <Badge variant="outline">{titleCase(item.verification_status)}</Badge>
                  ) : null}
                </div>
              </div>
              <Button
                type="button"
                variant="ghost"
                onClick={() => onChange(values.filter((_, rowIndex) => rowIndex !== index))}
              >
                <Trash2 className="h-4 w-4" />Remove
              </Button>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <Field label="Account holder">
                <Input
                  value={item.account_holder}
                  onChange={(event) => update(index, { account_holder: event.target.value })}
                />
              </Field>

              <Field label="Bank" hint="FNB, PB, STD or NB">
                <NativeSelect
                  value={item.bank_name}
                  onChange={(event) => {
                    const bankName = event.target.value;
                    const selected = bankDetails(bankName);
                    update(index, {
                      bank_name: bankName,
                      branch_name: selected?.branch ?? DEFAULT_BANK_BRANCH,
                      branch_code: selected?.code ?? null,
                    });
                  }}
                >
                  <option value="">Select bank</option>
                  {legacyBank ? <option value={legacyBank}>Legacy — {legacyBank}</option> : null}
                  {BANK_NAMES.map((bankName) => (
                    <option key={bankName} value={bankName}>{bankName}</option>
                  ))}
                </NativeSelect>
              </Field>

              <Field
                label="Account number"
                hint={item.id && !item.account_number
                  ? `Blank keeps the encrypted account number. ${bankAccountPrefixHint(item.bank_name)}`
                  : bankAccountPrefixHint(item.bank_name)}
                error={accountError}
              >
                <Input
                  type="password"
                  autoComplete="off"
                  inputMode="numeric"
                  value={item.account_number ?? ""}
                  onChange={(event) => update(index, { account_number: event.target.value || null })}
                  placeholder={item.id ? "Blank keeps encrypted number" : "Required for a new account"}
                  aria-invalid={accountError ? true : undefined}
                />
              </Field>

              <Field label="Branch" hint="Default for all supported banks">
                <Input value={branchValue} readOnly />
              </Field>

              <Field label="Bank code" hint="Filled automatically from the selected bank">
                <Input value={codeValue} readOnly placeholder="Select a bank" />
              </Field>

              <Field label="Account type">
                <NativeSelect
                  value={item.account_type}
                  onChange={(event) => update(index, { account_type: event.target.value })}
                >
                  <option value="savings">Savings</option>
                  <option value="current">Current / cheque</option>
                  <option value="transmission">Transmission</option>
                  <option value="business">Business</option>
                  <option value="other">Other</option>
                </NativeSelect>
              </Field>

              <Field label="Currency">
                <NativeSelect
                  value={item.currency}
                  onChange={(event) => update(index, { currency: event.target.value })}
                >
                  <option value="LSL">LSL — Lesotho loti</option>
                  <option value="ZAR">ZAR — South African rand</option>
                  <option value="USD">USD — US dollar</option>
                </NativeSelect>
              </Field>

              <label className="flex min-h-11 items-center gap-3 self-end rounded-xl border bg-background px-4 py-3">
                <input
                  type="checkbox"
                  checked={item.salary_account}
                  onChange={(event) => update(index, { salary_account: event.target.checked })}
                  className="h-4 w-4 accent-primary"
                />
                <span>
                  <span className="block text-sm font-bold">Salary account</span>
                  <span className="block text-xs text-muted-foreground">Regular income is paid here.</span>
                </span>
              </label>

              {allowVerification ? (
                <Field label="Verification status">
                  <NativeSelect
                    value={item.verification_status}
                    onChange={(event) => update(index, {
                      verification_status: event.target.value as BankAccountInput["verification_status"],
                    })}
                  >
                    <option value="unverified">Unverified</option>
                    <option value="pending">Pending</option>
                    <option value="verified">Verified</option>
                    <option value="failed">Failed</option>
                  </NativeSelect>
                </Field>
              ) : null}

              {allowVerification ? (
                <Field label="Verification reference">
                  <Input
                    value={item.verification_reference ?? ""}
                    onChange={(event) => update(index, { verification_reference: event.target.value || null })}
                  />
                </Field>
              ) : null}
            </div>

            {legacyBank ? (
              <div className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/20 dark:text-amber-200">
                This historical account uses <strong>{legacyBank}</strong>. It is preserved for existing data.
                Select FNB, PB, STD or NB only when deliberately migrating the banking record.
              </div>
            ) : null}

            {allowTokenizedCard ? (
              <div className="rounded-3xl border bg-background p-5">
                <h3 className="font-black">Tokenized card reference (optional)</h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  Store only a PCI-provider token and masked card metadata. Never store CVV/CVC or PIN.
                </p>
                <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <Input
                    value={item.tokenized_card_provider ?? ""}
                    onChange={(event) => update(index, { tokenized_card_provider: event.target.value || null })}
                    placeholder="Provider"
                  />
                  <Input
                    type="password"
                    value={item.tokenized_card_reference ?? ""}
                    onChange={(event) => update(index, { tokenized_card_reference: event.target.value || null })}
                    placeholder="Provider token"
                  />
                  <Input
                    value={item.masked_card_number ?? ""}
                    onChange={(event) => update(index, { masked_card_number: event.target.value || null })}
                    placeholder="Masked, e.g. **** 4832"
                  />
                  <Input
                    value={item.card_brand ?? ""}
                    onChange={(event) => update(index, { card_brand: event.target.value || null })}
                    placeholder="Card brand"
                  />
                </div>
              </div>
            ) : null}
          </section>
        );
      })}
    </div>
  );
}

function Field({
  label,
  children,
  hint,
  error,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
  error?: string | null;
}) {
  return (
    <label className="space-y-2">
      <span className="block text-sm font-bold">{label}</span>
      {children}
      {error ? <span className="block text-xs font-semibold text-destructive">{error}</span> : null}
      {!error && hint ? <span className="block text-xs text-muted-foreground">{hint}</span> : null}
    </label>
  );
}
