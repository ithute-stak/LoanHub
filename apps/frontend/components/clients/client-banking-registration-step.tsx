"use client";

import type { ReactNode } from "react";
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

function accountDigits(value: string | null | undefined): string {
  return String(value ?? "").replace(/\D/g, "").slice(0, 40);
}

function formatAccountNumber(value: string | null | undefined): string {
  return accountDigits(value).replace(/(\d{4})(?=\d)/g, "$1 ");
}

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

function BankField({
  label,
  required = false,
  hint,
  children,
  className = "",
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-2xl border border-border/60 bg-background p-3.5 shadow-sm transition-all duration-200 focus-within:border-primary/40 focus-within:ring-2 focus-within:ring-primary/10 ${className}`}>
      <div className="mb-2.5 space-y-1">
        <Label className="text-xs font-black tracking-[0.01em] text-foreground/90">
          {label}{required ? <span className="ml-1 text-destructive">*</span> : null}
        </Label>
        {hint ? <p className="text-[11px] leading-4 text-muted-foreground">{hint}</p> : null}
      </div>
      {children}
    </div>
  );
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
      <label
        htmlFor="capture-borrower-banking"
        className={`flex cursor-pointer items-start gap-4 rounded-3xl border p-4 transition-all duration-200 sm:p-5 ${
          enabled
            ? "border-primary/30 bg-gradient-to-br from-primary/10 via-background to-emerald-500/5 shadow-sm"
            : "border-border/60 bg-muted/20 hover:border-primary/25 hover:bg-muted/30"
        }`}
      >
        <span className={`mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${enabled ? "bg-primary text-primary-foreground" : "bg-background text-muted-foreground shadow-sm"}`}>
          <Landmark className="h-5 w-5" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-black">Capture banking details now</span>
            <span className={`rounded-full px-2.5 py-1 text-[10px] font-black uppercase tracking-wider ${enabled ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"}`}>
              {enabled ? "Enabled" : "Optional"}
            </span>
          </span>
          <span className="mt-1 block text-sm leading-5 text-muted-foreground">
            Record the borrower’s payout or salary account now, or add it later from the borrower profile.
          </span>
        </span>
        <Checkbox
          id="capture-borrower-banking"
          className="mt-2"
          checked={enabled}
          onCheckedChange={(checked) => onChange(checked ? emptyBankAccount(borrowerName) : null)}
        />
      </label>

      {value ? (
        <>
          <div className="rounded-3xl border border-border/60 bg-gradient-to-b from-card to-muted/10 p-4 shadow-sm sm:p-5">
            <div className="mb-5 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-base font-black tracking-tight">Primary bank account</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">Use the account exactly as it appears on the borrower’s bank records.</p>
              </div>
              <p className="text-[10px] font-black uppercase tracking-[0.14em] text-muted-foreground">Secure banking profile</p>
            </div>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <BankField label="Bank" required hint="Select the borrower’s bank first.">
                <Select value={value.bank_name || undefined} onValueChange={selectBank}>
                  <SelectTrigger className="h-12 w-full rounded-xl bg-background shadow-sm"><SelectValue placeholder="Select bank" /></SelectTrigger>
                  <SelectContent>
                    {BANK_OPTIONS.map((bank) => (
                      <SelectItem key={bank.value} value={bank.value}>{bank.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </BankField>

              <BankField
                label="Account number"
                required
                hint={selectedBank ? `Expected prefix: ${selectedBank.prefixes}` : "Select the bank to see the expected prefix."}
                className="md:col-span-1 xl:col-span-2"
              >
                <Input
                  aria-label="Bank account number"
                  className="h-12 rounded-xl bg-background px-4 font-mono text-base font-bold tracking-[0.12em] tabular-nums shadow-sm sm:text-lg"
                  inputMode="numeric"
                  enterKeyHint="next"
                  autoComplete="off"
                  spellCheck={false}
                  aria-describedby="bank-account-number-help"
                  value={formatAccountNumber(value.account_number)}
                  placeholder={selectedBank ? `e.g. ${selectedBank.prefixes === "6" ? "6000 1234 5678" : `${selectedBank.prefixes.split(" ")[0]}00 1234 5678`}` : "0000 0000 0000"}
                  onChange={(event) => {
                    const digits = accountDigits(event.target.value);
                    update("account_number", digits || null);
                  }}
                />
                <p id="bank-account-number-help" className="mt-2 text-[11px] leading-4 text-muted-foreground">
                  Spaces are added automatically while typing. Only normalized digits are submitted to LoanHub.
                </p>
              </BankField>

              <BankField label="Account holder" required hint="Name registered against this account.">
                <Input
                  className="h-12 rounded-xl bg-background shadow-sm"
                  autoFocus
                  autoComplete="name"
                  autoCapitalize="words"
                  value={value.account_holder}
                  onChange={(event) => update("account_holder", event.target.value)}
                />
              </BankField>

              <BankField label="Account type">
                <Select value={value.account_type || "savings"} onValueChange={(nextValue) => update("account_type", nextValue)}>
                  <SelectTrigger className="h-12 w-full rounded-xl bg-background shadow-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="savings">Savings</SelectItem>
                    <SelectItem value="current">Current</SelectItem>
                    <SelectItem value="cheque">Cheque</SelectItem>
                  </SelectContent>
                </Select>
              </BankField>

              <BankField label="Currency">
                <Select value={value.currency || "LSL"} onValueChange={(nextValue) => update("currency", nextValue)}>
                  <SelectTrigger className="h-12 w-full rounded-xl bg-background shadow-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="LSL">LSL — Lesotho loti</SelectItem>
                    <SelectItem value="ZAR">ZAR — South African rand</SelectItem>
                  </SelectContent>
                </Select>
              </BankField>
            </div>

            <label className={`mt-3 flex cursor-pointer items-start gap-3 rounded-2xl border p-4 transition ${value.salary_account ? "border-primary/30 bg-primary/5" : "border-border/60 bg-background hover:border-primary/25"}`}>
              <Checkbox
                aria-label="Salary or primary income account"
                className="mt-0.5"
                checked={value.salary_account}
                onCheckedChange={(checked) => update("salary_account", Boolean(checked))}
              />
              <span className="min-w-0">
                <span className="block text-sm font-black">Salary / primary income account</span>
                <span className="mt-1 block text-xs leading-5 text-muted-foreground">Mark this when the borrower normally receives salary or primary income into this account.</span>
              </span>
            </label>
          </div>

          {selectedBank ? (
            <div className="grid gap-3 rounded-2xl border border-primary/15 bg-primary/5 p-4 text-sm sm:grid-cols-3">
              <div><p className="text-[10px] font-black uppercase tracking-wider text-muted-foreground">Routing branch</p><p className="mt-1 font-black">Maseru Central</p></div>
              <div><p className="text-[10px] font-black uppercase tracking-wider text-muted-foreground">Branch code</p><p className="mt-1 font-mono font-black tabular-nums">{selectedBank.branchCode}</p></div>
              <div><p className="text-[10px] font-black uppercase tracking-wider text-muted-foreground">Account prefix</p><p className="mt-1 font-mono font-black tabular-nums">{selectedBank.prefixes}</p></div>
            </div>
          ) : null}

          <Alert className="rounded-2xl border-emerald-500/20 bg-emerald-500/5">
            <ShieldCheck className="h-4 w-4" />
            <AlertTitle>Banking data protection</AlertTitle>
            <AlertDescription>
              LoanHub stores the full account number encrypted and shows only masked or last-four details in normal client views. New banking details remain unverified until the formal KYC/verification step.
            </AlertDescription>
          </Alert>
        </>
      ) : (
        <div className="flex min-h-40 flex-col items-center justify-center rounded-3xl border border-dashed border-border/70 bg-muted/10 p-6 text-center">
          <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
            <Landmark className="h-6 w-6" />
          </span>
          <p className="font-black">No banking details captured</p>
          <p className="mt-1 max-w-lg text-sm leading-5 text-muted-foreground">
            The borrower can still be registered. Enable banking capture above when the account details are available.
          </p>
        </div>
      )}
    </div>
  );
}
