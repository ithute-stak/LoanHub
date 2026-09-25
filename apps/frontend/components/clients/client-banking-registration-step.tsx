"use client";

import { Landmark, ShieldCheck } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { BankAccountInput } from "@/types/origination";


type ClientBankingRegistrationStepProps = {
  value: BankAccountInput | null | undefined;
  borrowerName: string;
  onChange: (value: BankAccountInput | null) => void;
};

const BANK_OPTIONS = [
  { value: "FNB", label: "FNB — First National Bank Lesotho", branchCode: "280061", prefixes: "6" },
  { value: "PB", label: "PB — Lesotho PostBank", branchCode: "500100", prefixes: "10" },
  { value: "STD", label: "STD — Standard Lesotho Bank", branchCode: "060667", prefixes: "90" },
  { value: "NB", label: "NB — Nedbank Lesotho", branchCode: "390161", prefixes: "11 or 12" },
] as const;

function emptyBankAccount(borrowerName: string): BankAccountInput {
  return {
    account_holder: borrowerName.trim(),
    bank_name: "",
    branch_name: null,
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

export function ClientBankingRegistrationStep({
  value,
  borrowerName,
  onChange,
}: ClientBankingRegistrationStepProps) {
  const enabled = Boolean(value);
  const selectedBank = BANK_OPTIONS.find((bank) => bank.value === value?.bank_name) ?? null;

  function update<K extends keyof BankAccountInput>(key: K, nextValue: BankAccountInput[K]) {
    if (!value) return;
    onChange({ ...value, [key]: nextValue });
  }

  function selectBank(bankName: string) {
    if (!value) return;
    const bank = BANK_OPTIONS.find((option) => option.value === bankName);
    onChange({
      ...value,
      bank_name: bankName,
      branch_name: bank ? "Maseru Central" : null,
      branch_code: bank?.branchCode ?? null,
    });
  }

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border bg-muted/15 p-4 sm:p-5">
        <div className="flex items-start gap-3">
          <Checkbox
            id="capture-borrower-banking"
            checked={enabled}
            onCheckedChange={(checked) => onChange(checked ? emptyBankAccount(borrowerName) : null)}
          />
          <div className="min-w-0">
            <Label htmlFor="capture-borrower-banking" className="cursor-pointer font-black">
              Capture banking details now
            </Label>
            <p className="mt-1 text-sm leading-5 text-muted-foreground">
              Banking details can be captured during registration or added later from the borrower profile.
            </p>
          </div>
        </div>
      </div>

      {value ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <div className="space-y-2">
              <Label>Account holder <span className="text-destructive">*</span></Label>
              <Input
                className="h-11"
                autoFocus
                autoComplete="name"
                value={value.account_holder}
                onChange={(event) => update("account_holder", event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Bank <span className="text-destructive">*</span></Label>
              <Select value={value.bank_name || undefined} onValueChange={selectBank}>
                <SelectTrigger className="h-11 w-full"><SelectValue placeholder="Select bank" /></SelectTrigger>
                <SelectContent>
                  {BANK_OPTIONS.map((bank) => (
                    <SelectItem key={bank.value} value={bank.value}>{bank.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Account number <span className="text-destructive">*</span></Label>
              <Input
                className="h-11 font-mono"
                inputMode="numeric"
                autoComplete="off"
                value={value.account_number ?? ""}
                placeholder={selectedBank ? `Starts with ${selectedBank.prefixes}` : "Select the bank first"}
                onChange={(event) => update("account_number", event.target.value)}
              />
              <p className="text-xs text-muted-foreground">The full account number is encrypted at rest.</p>
            </div>
            <div className="space-y-2">
              <Label>Account type</Label>
              <Select value={value.account_type || "savings"} onValueChange={(nextValue) => update("account_type", nextValue)}>
                <SelectTrigger className="h-11 w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="savings">Savings</SelectItem>
                  <SelectItem value="current">Current</SelectItem>
                  <SelectItem value="cheque">Cheque</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Currency</Label>
              <Select value={value.currency || "LSL"} onValueChange={(nextValue) => update("currency", nextValue)}>
                <SelectTrigger className="h-11 w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="LSL">LSL — Lesotho loti</SelectItem>
                  <SelectItem value="ZAR">ZAR — South African rand</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <label className="flex min-h-11 items-center gap-3 rounded-xl border bg-background px-4 py-3 md:col-span-2 xl:col-span-2">
              <Checkbox
                aria-label="Salary or primary income account"
                checked={value.salary_account}
                onCheckedChange={(checked) => update("salary_account", Boolean(checked))}
              />
              <span>
                <span className="block text-sm font-bold">Salary / primary income account (optional)</span>
                <span className="block text-xs text-muted-foreground">Mark this when the borrower normally receives salary or primary income into this account.</span>
              </span>
            </label>
          </div>

          {selectedBank ? (
            <div className="rounded-2xl border bg-muted/15 p-4 text-sm">
              <p className="font-black">LoanHub routing details</p>
              <p className="mt-1 text-muted-foreground">
                Maseru Central · branch code {selectedBank.branchCode} · accepted account prefix {selectedBank.prefixes}.
              </p>
            </div>
          ) : null}

          <Alert>
            <ShieldCheck className="h-4 w-4" />
            <AlertTitle>Banking data protection</AlertTitle>
            <AlertDescription>
              LoanHub stores the bank account number encrypted and exposes only masked/last-four details in normal client views. Registration captures the details as unverified; formal verification remains a separate lending/KYC control.
            </AlertDescription>
          </Alert>
        </>
      ) : (
        <div className="flex min-h-36 flex-col items-center justify-center rounded-2xl border border-dashed bg-muted/10 p-6 text-center">
          <Landmark className="mb-3 h-8 w-8 text-muted-foreground" />
          <p className="font-black">No banking details captured</p>
          <p className="mt-1 max-w-lg text-sm text-muted-foreground">
            Continue without banking details, or enable banking capture above if the borrower has the information available.
          </p>
        </div>
      )}
    </div>
  );
}
