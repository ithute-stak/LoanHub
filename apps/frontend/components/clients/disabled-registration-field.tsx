"use client";

import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import type { RegistrationFieldRequirement } from "@/api/batlokoaRegistration";

const NO_CAPTURE = "Available after release approval";

function label(key: string): string {
  return key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function textPlaceholder(kind: RegistrationFieldRequirement["kind"]): string {
  if (kind === "date") return "Date entry disabled";
  if (kind === "currency") return "LSL amount entry disabled";
  if (kind === "integer") return "Number entry disabled";
  if (kind === "uuid") return "Select from authorized company records";
  if (kind === "password") return "Credential setup disabled";
  if (kind === "select") return "Choose an option after release";
  return "Entry disabled until registration is approved";
}

/**
 * Pure presentation prototype. Every control is disabled, has no onChange,
 * and has no value or defaultValue. It must never collect live borrower PII.
 */
export function DisabledRegistrationField({
  field,
}: {
  field: RegistrationFieldRequirement;
}) {
  const labelText = label(field.key);
  const id = `registration-preview-${field.key}`;
  if (field.kind === "bank_account" || field.kind === "debt_list" ||
      field.kind === "employer_group") {
    return (
      <div className="space-y-2 rounded-xl border bg-muted/20 p-4">
        <Label>{labelText}</Label>
        <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
          {field.kind === "bank_account"
            ? "Bank, account holder, account number and verification details will use the protected banking workflow."
            : field.kind === "debt_list"
              ? "Declared external debts will be entered as separate obligations, not new LoanHub loans."
              : "Company employer-group selection or creation requires separate authorization."}
        </div>
        <p className="text-xs text-muted-foreground">{NO_CAPTURE}</p>
      </div>
    );
  }

  if (field.kind === "boolean") {
    return (
      <div className="space-y-2 rounded-xl border bg-muted/20 p-4">
        <div className="flex items-center gap-3">
          <Checkbox id={id} disabled checked={false} />
          <Label htmlFor={id}>{labelText}</Label>
        </div>
        <p className="text-xs text-muted-foreground">
          {field.key.startsWith("consent_")
            ? "Consent must be obtained from the client in an approved registration session."
            : NO_CAPTURE}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2 rounded-xl border bg-muted/20 p-4">
      <Label htmlFor={id}>{labelText}</Label>
      <Input
        id={id}
        disabled
        readOnly
        type={field.kind === "date" ? "date" : "text"}
        placeholder={textPlaceholder(field.kind)}
        autoComplete="off"
        aria-describedby={`${id}-notice`}
      />
      <p id={`${id}-notice`} className="text-xs text-muted-foreground">
        {field.deferred ? "Requires further independent certification." : NO_CAPTURE}
        {field.sensitive ? " Protected personal information." : ""}
      </p>
    </div>
  );
}
