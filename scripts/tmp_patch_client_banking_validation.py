from pathlib import Path


path = Path("apps/frontend/app/(dashboard)/company/clients/page.tsx")
text = path.read_text()

old_validation = '''    if (step === 3) {
      const bank = clientForm.bank_account;
      if (bank) {
        const accountNumber = String(bank.account_number ?? "").replace(/\\s+/g, "");
        if (!bank.account_holder.trim()) errors.push("Enter the bank account holder.");
        if (!bank.bank_name.trim()) errors.push("Enter the borrower’s bank name.");
        if (accountNumber.length < 4) errors.push("Enter a valid bank account number.");
      }
    }'''
new_validation = '''    if (step === 3) {
      const bank = clientForm.bank_account;
      if (bank) {
        const accountNumber = String(bank.account_number ?? "").replace(/[\\s/-]+/g, "");
        const bankPrefixes: Record<string, string[]> = {
          FNB: ["6"],
          PB: ["10"],
          STD: ["90"],
          NB: ["11", "12"],
        };
        if (bank.account_holder.trim().length < 2) errors.push("Enter the bank account holder.");
        if (!bank.bank_name.trim() || !bankPrefixes[bank.bank_name]) errors.push("Select a supported borrower bank.");
        if (accountNumber.length < 4) {
          errors.push("Enter a valid bank account number.");
        } else if (!/^\\d+$/.test(accountNumber)) {
          errors.push("The bank account number must contain digits only.");
        } else {
          const prefixes = bankPrefixes[bank.bank_name] ?? [];
          if (prefixes.length > 0 && !prefixes.some((prefix) => accountNumber.startsWith(prefix))) {
            errors.push(`${bank.bank_name} account number must start with ${prefixes.join(" or ")}.`);
          }
        }
      }
    }'''

if text.count(old_validation) != 1:
    raise SystemExit(f"bank validation: expected 1 match, found {text.count(old_validation)}")
text = text.replace(old_validation, new_validation, 1)

old_normalize = '            account_number: optional(clientForm.bank_account.account_number)?.replace(/\\s+/g, "") ?? null,'
new_normalize = '            account_number: optional(clientForm.bank_account.account_number)?.replace(/[\\s/-]+/g, "") ?? null,'
if text.count(old_normalize) != 1:
    raise SystemExit(f"account normalization: expected 1 match, found {text.count(old_normalize)}")
text = text.replace(old_normalize, new_normalize, 1)

old_review = '                            <ReviewItem label="Account" value={clientForm.bank_account?.account_number ? `••••${String(clientForm.bank_account.account_number).replace(/\\s+/g, "").slice(-4)}` : "Not supplied"} />'
new_review = '                            <ReviewItem label="Account" value={clientForm.bank_account?.account_number ? `••••${String(clientForm.bank_account.account_number).replace(/[\\s/-]+/g, "").slice(-4)}` : "Not supplied"} />'
if text.count(old_review) != 1:
    raise SystemExit(f"review masking: expected 1 match, found {text.count(old_review)}")
text = text.replace(old_review, new_review, 1)

path.write_text(text)
print("Supported-bank validation applied")
