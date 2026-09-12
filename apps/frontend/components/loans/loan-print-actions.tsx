"use client";

import { useMemo, useState, type FormEvent } from "react";
import {
  FileSignature,
  Loader2,
  Printer,
  Search,
  UserRoundSearch,
} from "lucide-react";

import { listCompanyClients } from "@/api/companyClients";
import { getLoanByReference } from "@/api/loans";
import { originationApi } from "@/api/origination";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { markDocumentGenerationFailed, prepareDocumentGenerationWindow } from "@/lib/document-generation-overlay";
import { formatDate, formatMoney, titleCase } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";
import type { CompanyClient } from "@/types/companyClient";
import type { Loan } from "@/types/loan";
import type { LoanContract } from "@/types/origination";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const CONTRACT_ELIGIBLE_STATUSES = new Set<Loan["status"]>([
  "approved",
  "active",
  "defaulted",
  "completed",
]);

type LoanLookup = {
  loan: Loan;
  borrower: CompanyClient | null;
};

export function LoanPrintActions({ loans }: { loans: Loan[] }) {
  const { currentCompany, currentBranch } = useAppData();

  const [loanDialogOpen, setLoanDialogOpen] = useState(false);
  const [loanNumber, setLoanNumber] = useState("");
  const [loanLookup, setLoanLookup] = useState<LoanLookup | null>(null);
  const [loanLoading, setLoanLoading] = useState(false);

  const [contractDialogOpen, setContractDialogOpen] = useState(false);
  const [borrowerQuery, setBorrowerQuery] = useState("");
  const [borrowers, setBorrowers] = useState<CompanyClient[]>([]);
  const [selectedBorrower, setSelectedBorrower] = useState<CompanyClient | null>(null);
  const [borrowerSearching, setBorrowerSearching] = useState(false);
  const [contractsLoading, setContractsLoading] = useState(false);
  const [contracts, setContracts] = useState<LoanContract[]>([]);
  const [workingLoanId, setWorkingLoanId] = useState<string | null>(null);

  const selectedBorrowerLoans = useMemo(() => {
    if (!selectedBorrower) return [];
    return loans.filter((loan) => loan.borrower_id === selectedBorrower.borrower_id);
  }, [loans, selectedBorrower]);

  async function lookupLoan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const reference = loanNumber.trim();
    if (!reference) {
      toast.warning("Enter a loan number first.");
      return;
    }

    setLoanLoading(true);
    setLoanLookup(null);
    try {
      const loan = await getLoanByReference(reference);
      const borrower = await listCompanyClients()
        .then((rows) => rows.find((item) => item.borrower_id === loan.borrower_id) ?? null)
        .catch(() => null);
      setLoanLookup({ loan, borrower });
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The loan number was not found."));
    } finally {
      setLoanLoading(false);
    }
  }

  async function openContractSearch() {
    setContractDialogOpen(true);
    setContractsLoading(true);
    try {
      setContracts(await originationApi.listContracts());
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Existing contracts could not be loaded."));
    } finally {
      setContractsLoading(false);
    }
  }

  async function searchBorrowers(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = borrowerQuery.trim();
    if (query.length < 2) {
      toast.warning("Enter at least two letters from the borrower name.");
      return;
    }

    setBorrowerSearching(true);
    setSelectedBorrower(null);
    try {
      const rows = await listCompanyClients({ search: query });
      setBorrowers(rows);
      if (rows.length === 0) {
        toast.info("No borrower matched that name.");
      }
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Borrower search could not be completed."));
    } finally {
      setBorrowerSearching(false);
    }
  }

  async function printContract(loan: Loan) {
    const printWindow = window.open("", "_blank", "width=1100,height=850");
    if (!printWindow) {
      toast.error("The print window was blocked. Allow pop-ups for LoanHub and try again.");
      return;
    }

    prepareDocumentGenerationWindow(printWindow, {
      title: `Preparing ${loan.loan_reference} contract`,
      description: "Please wait while LoanHub loads or generates the current loan contract.",
      companyId: loan.company_id,
    });

    setWorkingLoanId(loan.id);
    try {
      let contract = contracts.find((item) => item.loan_id === loan.id);
      if (!contract) {
        const created = await originationApi.generateContract(loan.id, null);
        contract = created;
        setContracts((current) => [
          created,
          ...current.filter((item) => item.id !== created.id),
        ]);
      }
      await originationApi.openContractForPrinting(contract, printWindow);
      toast.success("Contract opened", {
        description: "Use the browser PDF toolbar to print or save the agreement.",
      });
    } catch (error: unknown) {
      markDocumentGenerationFailed(
        printWindow,
        "The contract could not be prepared. Return to LoanHub, review the error message and try again.",
      );
      toast.error(getErrorMessage(error, "The contract could not be opened for printing."));
    } finally {
      setWorkingLoanId(null);
    }
  }

  return (
    <>
      <Button variant="outline" onClick={() => setLoanDialogOpen(true)}>
        <Printer className="h-4 w-4" />
        Print loan info
      </Button>
      <Button variant="outline" onClick={() => void openContractSearch()}>
        <FileSignature className="h-4 w-4" />
        Print contract
      </Button>

      <CustomDialog
        open={loanDialogOpen}
        onOpenChange={(open) => {
          setLoanDialogOpen(open);
          if (!open) setLoanLookup(null);
        }}
        title="Print loan information"
        description="Enter the exact loan number to retrieve the latest balance and repayment schedule."
        contentClassName="sm:max-w-4xl"
      >
        <div className="space-y-5 p-6 sm:p-8">
          <form onSubmit={lookupLoan} className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1 space-y-2">
              <Label htmlFor="print-loan-number">Loan number</Label>
              <Input
                id="print-loan-number"
                value={loanNumber}
                onChange={(event) => setLoanNumber(event.target.value.toUpperCase())}
                placeholder="LBBFS8F3K29"
                autoComplete="off"
              />
            </div>
            <LoadingButton type="submit" loading={loanLoading} loadingText="Searching..." className="sm:min-w-36">
              <Search className="h-4 w-4" />
              Find loan
            </LoadingButton>
          </form>

          {loanLookup ? (
            <div className="space-y-5">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <PrintValue label="Borrower" value={loanLookup.borrower?.full_name ?? "Borrower profile unavailable"} />
                <PrintValue label="Principal" value={formatMoney(loanLookup.loan.principal_amount)} />
                <PrintValue label="Outstanding" value={formatMoney(loanLookup.loan.balance)} emphasis />
                <PrintValue label="Status" value={titleCase(loanLookup.loan.status)} />
              </div>

              <div className="overflow-x-auto rounded-2xl border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>#</TableHead>
                      <TableHead>Due date</TableHead>
                      <TableHead>Principal</TableHead>
                      <TableHead>Interest</TableHead>
                      <TableHead>Total</TableHead>
                      <TableHead>Paid</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {loanLookup.loan.installments.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="font-black">{item.installment_number}</TableCell>
                        <TableCell>{formatDate(item.due_date)}</TableCell>
                        <TableCell>{formatMoney(item.principal_due)}</TableCell>
                        <TableCell>{formatMoney(item.interest_due)}</TableCell>
                        <TableCell className="font-black">{formatMoney(item.total_due)}</TableCell>
                        <TableCell>{formatMoney(item.paid_amount)}</TableCell>
                        <TableCell><Badge variant={item.status === "paid" ? "default" : "secondary"}>{titleCase(item.status)}</Badge></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          ) : null}

          <DialogFooter className="mx-0 mb-0 flex-wrap">
            <Button variant="outline" onClick={() => setLoanDialogOpen(false)}>Close</Button>
            {loanLookup ? (
              <Button
                onClick={() => printLoanInformation({
                  lookup: loanLookup,
                  companyName: currentCompany?.name ?? "Loan company",
                  companyPhone: currentCompany?.phone ?? null,
                  companyEmail: currentCompany?.email ?? null,
                  companyAddress: currentCompany?.address ?? null,
                  companyLicense: currentCompany?.license_number ?? null,
                  branchName: currentBranch?.name ?? null,
                })}
              >
                <Printer className="h-4 w-4" />
                Print loan information
              </Button>
            ) : null}
          </DialogFooter>
        </div>
      </CustomDialog>

      <CustomDialog
        open={contractDialogOpen}
        onOpenChange={(open) => {
          setContractDialogOpen(open);
          if (!open) {
            setBorrowers([]);
            setSelectedBorrower(null);
          }
        }}
        title="Find borrower and print contract"
        description="Search the borrower by name. LoanHub returns the borrower account and user ID, then shows every matching company loan."
        contentClassName="sm:max-w-4xl"
      >
        <div className="space-y-5 p-6 sm:p-8">
          <form onSubmit={searchBorrowers} className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1 space-y-2">
              <Label htmlFor="contract-borrower-name">Borrower name</Label>
              <Input
                id="contract-borrower-name"
                value={borrowerQuery}
                onChange={(event) => setBorrowerQuery(event.target.value)}
                placeholder="First name, surname or full name"
                autoComplete="off"
              />
            </div>
            <LoadingButton type="submit" loading={borrowerSearching} loadingText="Searching..." className="sm:min-w-40">
              <UserRoundSearch className="h-4 w-4" />
              Search borrower
            </LoadingButton>
          </form>

          {contractsLoading ? (
            <div className="flex items-center justify-center gap-2 rounded-2xl border border-dashed p-8 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading existing contracts...
            </div>
          ) : null}

          {borrowers.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {borrowers.map((borrower) => (
                <button
                  key={borrower.id}
                  type="button"
                  onClick={() => setSelectedBorrower(borrower)}
                  className={`rounded-2xl border p-4 text-left transition hover:border-primary/50 hover:bg-primary/5 ${selectedBorrower?.id === borrower.id ? "border-primary bg-primary/5" : ""}`}
                >
                  <p className="font-black">{borrower.full_name}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{borrower.phone}{borrower.email ? ` · ${borrower.email}` : ""}</p>
                  <p className="mt-2 break-all font-mono text-[11px] text-muted-foreground">User ID: {borrower.user_id}</p>
                </button>
              ))}
            </div>
          ) : null}

          {selectedBorrower ? (
            <div className="space-y-4">
              <Alert>
                <FileSignature className="h-4 w-4" />
                <AlertTitle>{selectedBorrower.full_name}</AlertTitle>
                <AlertDescription>
                  Borrower user ID: <span className="font-mono">{selectedBorrower.user_id}</span>. Select the loan whose agreement must be printed.
                </AlertDescription>
              </Alert>

              {selectedBorrowerLoans.length === 0 ? (
                <div className="rounded-2xl border border-dashed p-8 text-center text-sm text-muted-foreground">
                  No loan in the current company portfolio is linked to this borrower.
                </div>
              ) : (
                <div className="space-y-3">
                  {selectedBorrowerLoans.map((loan) => {
                    const contract = contracts.find((item) => item.loan_id === loan.id);
                    const canGenerate = CONTRACT_ELIGIBLE_STATUSES.has(loan.status);
                    const disabled = workingLoanId !== null || (!contract && !canGenerate);
                    return (
                      <div key={loan.id} className="flex flex-col gap-4 rounded-2xl border p-4 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <p className="font-mono text-xs font-black text-primary">{loan.loan_reference}</p>
                          <p className="mt-2 font-black">{formatMoney(loan.principal_amount)} · {titleCase(loan.status)}</p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {contract ? `Contract ${contract.contract_number} · ${titleCase(contract.status)}` : "No contract generated yet"}
                          </p>
                        </div>
                        <LoadingButton
                          loading={workingLoanId === loan.id}
                          loadingText={contract ? "Opening..." : "Generating..."}
                          disabled={disabled}
                          onClick={() => void printContract(loan)}
                          className="sm:min-w-44"
                        >
                          <Printer className="h-4 w-4" />
                          {contract ? "Print contract" : "Generate & print"}
                        </LoadingButton>
                        {!contract && !canGenerate ? (
                          <p className="text-xs text-amber-700 sm:max-w-48">A contract cannot be generated while the loan is {titleCase(loan.status)}.</p>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ) : null}

          <DialogFooter className="mx-0 mb-0">
            <Button variant="outline" onClick={() => setContractDialogOpen(false)}>Close</Button>
          </DialogFooter>
        </div>
      </CustomDialog>
    </>
  );
}

function PrintValue({ label, value, emphasis = false }: { label: string; value: string; emphasis?: boolean }) {
  return (
    <div className="rounded-2xl border bg-background/70 p-4">
      <p className="text-xs font-black uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <p className={`mt-1 font-black ${emphasis ? "text-xl text-primary" : "text-base"}`}>{value}</p>
    </div>
  );
}

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function printLoanInformation({
  lookup,
  companyName,
  companyPhone,
  companyEmail,
  companyAddress,
  companyLicense,
  branchName,
}: {
  lookup: LoanLookup;
  companyName: string;
  companyPhone: string | null;
  companyEmail: string | null;
  companyAddress: string | null;
  companyLicense: string | null;
  branchName: string | null;
}) {
  const popup = window.open("", "_blank", "width=1100,height=850");
  if (!popup) {
    toast.error("The print window was blocked. Allow pop-ups for LoanHub and try again.");
    return;
  }

  const { loan, borrower } = lookup;
  const progress = Number(loan.total_repayable) > 0
    ? (Number(loan.amount_paid) / Number(loan.total_repayable)) * 100
    : 0;
  const logoUrl = `${window.location.origin}/loanhub-horizontal-logo.png`;
  const rows = loan.installments.map((item) => `
    <tr>
      <td>${item.installment_number}</td>
      <td>${escapeHtml(formatDate(item.due_date))}</td>
      <td>${escapeHtml(formatMoney(item.principal_due))}</td>
      <td>${escapeHtml(formatMoney(item.interest_due))}</td>
      <td>${escapeHtml(formatMoney(item.fee_due))}</td>
      <td><strong>${escapeHtml(formatMoney(item.total_due))}</strong></td>
      <td>${escapeHtml(formatMoney(item.paid_amount))}</td>
      <td>${escapeHtml(titleCase(item.status))}</td>
    </tr>
  `).join("");

  popup.document.open();
  popup.document.write(`<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(loan.loan_reference)} - Loan Information</title>
  <style>
    * { box-sizing: border-box; }
    @page { size: A4; margin: 15mm; }
    body { margin: 0; color: #172b4d; font-family: Arial, Helvetica, sans-serif; background: #eef4f8; }
    .sheet { width: 210mm; min-height: 297mm; margin: 16px auto; padding: 15mm; background: #fff; }
    .header { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; border-bottom: 3px solid #0b69b7; padding-bottom: 12px; }
    .logo { width: 165px; max-height: 52px; object-fit: contain; object-position: left center; }
    .company { text-align: right; font-size: 11px; line-height: 1.55; color: #52606d; }
    h1 { margin: 20px 0 4px; color: #062b55; font-size: 24px; }
    .reference { margin: 0 0 18px; color: #0b69b7; font-family: monospace; font-size: 12px; font-weight: 700; }
    .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 14px 0; }
    .card { border: 1px solid #cfdae6; border-radius: 10px; padding: 10px; background: #f8fbfd; }
    .label { color: #52606d; font-size: 8px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
    .value { margin-top: 5px; font-size: 13px; font-weight: 700; }
    h2 { margin: 22px 0 10px; padding-bottom: 6px; border-bottom: 1px solid #cfdae6; color: #062b55; font-size: 15px; }
    table { width: 100%; border-collapse: collapse; font-size: 8.5px; }
    th { background: #062b55; color: #fff; padding: 7px 5px; text-align: left; }
    td { border-bottom: 1px solid #dde5ed; padding: 7px 5px; vertical-align: top; }
    .footer { margin-top: 24px; padding-top: 10px; border-top: 1px solid #cfdae6; display: flex; justify-content: space-between; color: #6b7785; font-size: 8px; }
    .note { margin-top: 16px; border-left: 4px solid #0f8b8d; padding: 10px 12px; background: #e9f7f5; font-size: 9px; line-height: 1.5; }
    @media print {
      body { background: #fff; }
      .sheet { width: auto; min-height: auto; margin: 0; padding: 0; }
    }
  </style>
</head>
<body>
  <main class="sheet">
    <header class="header">
      <img class="logo" src="${escapeHtml(logoUrl)}" alt="LoanHub" />
      <div class="company">
        <strong>${escapeHtml(companyName)}</strong><br />
        ${companyLicense ? `Licence: ${escapeHtml(companyLicense)}<br />` : ""}
        ${branchName ? `${escapeHtml(branchName)}<br />` : ""}
        ${companyAddress ? `${escapeHtml(companyAddress)}<br />` : ""}
        ${companyPhone ? `${escapeHtml(companyPhone)}<br />` : ""}
        ${companyEmail ? escapeHtml(companyEmail) : ""}
      </div>
    </header>

    <h1>Loan Information Statement</h1>
    <p class="reference">${escapeHtml(loan.loan_reference)}</p>

    <section class="grid">
      <div class="card"><div class="label">Borrower</div><div class="value">${escapeHtml(borrower?.full_name ?? "Not available")}</div></div>
      <div class="card"><div class="label">Borrower user ID</div><div class="value" style="font-size:9px;word-break:break-all">${escapeHtml(borrower?.user_id ?? "Not available")}</div></div>
      <div class="card"><div class="label">Loan status</div><div class="value">${escapeHtml(titleCase(loan.status))}</div></div>
      <div class="card"><div class="label">Progress</div><div class="value">${progress.toFixed(1)}%</div></div>
    </section>

    <h2>Loan summary</h2>
    <section class="grid">
      <div class="card"><div class="label">Principal</div><div class="value">${escapeHtml(formatMoney(loan.principal_amount))}</div></div>
      <div class="card"><div class="label">Interest rate</div><div class="value">${escapeHtml(String(loan.interest_rate))}%</div></div>
      <div class="card"><div class="label">Processing fee</div><div class="value">${escapeHtml(formatMoney(loan.processing_fee))}</div></div>
      <div class="card"><div class="label">Total repayable</div><div class="value">${escapeHtml(formatMoney(loan.total_repayable))}</div></div>
      <div class="card"><div class="label">Instalment</div><div class="value">${escapeHtml(formatMoney(loan.installment_amount))}</div></div>
      <div class="card"><div class="label">Amount paid</div><div class="value">${escapeHtml(formatMoney(loan.amount_paid))}</div></div>
      <div class="card"><div class="label">Outstanding balance</div><div class="value">${escapeHtml(formatMoney(loan.balance))}</div></div>
      <div class="card"><div class="label">Maturity date</div><div class="value">${escapeHtml(loan.maturity_date ? formatDate(loan.maturity_date) : "Not recorded")}</div></div>
    </section>

    <h2>Repayment schedule</h2>
    <table>
      <thead><tr><th>#</th><th>Due date</th><th>Principal</th><th>Interest</th><th>Fees</th><th>Total</th><th>Paid</th><th>Status</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="8">No repayment schedule is available.</td></tr>'}</tbody>
    </table>

    <div class="note">This statement reflects the information currently recorded in LoanHub. It is not a replacement for the signed credit agreement or an early-settlement quotation.</div>

    <footer class="footer">
      <span>Generated by LoanHub on ${escapeHtml(new Date().toLocaleString())}</span>
      <span>${escapeHtml(loan.loan_reference)}</span>
    </footer>
  </main>
</body>
</html>`);
  popup.document.close();
  popup.focus();
  window.setTimeout(() => popup.print(), 500);
}
