export const DEFAULT_BANK_BRANCH = "Maseru Central" as const;

export const BANKING_POLICY = {
  FNB: { code: "280061", prefixes: ["6"] },
  PB: { code: "500100", prefixes: ["10"] },
  STD: { code: "060667", prefixes: ["90"] },
  NB: { code: "390161", prefixes: ["11", "12"] },
} as const;

export type BankName = keyof typeof BANKING_POLICY;

export const BANK_NAMES = Object.keys(BANKING_POLICY) as BankName[];

export function isBankName(value: string | null | undefined): value is BankName {
  return Boolean(value && Object.prototype.hasOwnProperty.call(BANKING_POLICY, value));
}

export function bankDetails(bankName: string | null | undefined) {
  if (!isBankName(bankName)) return null;
  return {
    name: bankName,
    code: BANKING_POLICY[bankName].code,
    prefixes: BANKING_POLICY[bankName].prefixes,
    branch: DEFAULT_BANK_BRANCH,
  };
}

export function normalizeBankAccountNumber(value: string | null | undefined): string {
  return String(value ?? "").replace(/[\s/-]+/g, "");
}

export function bankAccountValidationMessage(
  bankName: string | null | undefined,
  accountNumber: string | null | undefined,
): string | null {
  const details = bankDetails(bankName);
  const normalized = normalizeBankAccountNumber(accountNumber);

  if (!details || !normalized) return null;
  if (!/^\d+$/.test(normalized)) return "Bank account number must contain digits only.";
  if (!details.prefixes.some((prefix) => normalized.startsWith(prefix))) {
    return `${details.name} account number must start with ${details.prefixes.join(" or ")}.`;
  }
  return null;
}

export function bankAccountPrefixHint(bankName: string | null | undefined): string {
  const details = bankDetails(bankName);
  if (!details) return "Select a bank to see the required account prefix.";
  return `${details.name} accounts must start with ${details.prefixes.join(" or ")}.`;
}
