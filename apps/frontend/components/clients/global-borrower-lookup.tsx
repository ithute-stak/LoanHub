"use client";

import { useRouter } from "next/navigation";
import {
  CircleCheckBig,
  History,
  IdCard,
  LoaderCircle,
  Printer,
  Search,
  ShieldCheck,
  TriangleAlert,
  UserRoundPlus,
} from "lucide-react";
import { useState, type FormEvent } from "react";

import {
  checkCompanyClientExistingLoans,
  getCompanyClientProfile,
} from "@/api/companyClients";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  markDocumentGenerationFailed,
  prepareDocumentGenerationWindow,
} from "@/lib/document-generation-overlay";
import { renderBorrowerHistoryReport } from "@/lib/borrower-history-report";
import { formatDate, formatMoney } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";
import type { CompanyClientExistingLoanCheck } from "@/types/companyClient";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";
import {
  borrowerLookupHref,
  dispatchGlobalBorrowerLookup,
  type GlobalBorrowerLookupAction,
} from "@/utils/borrowerLookup";

const MINIMUM_NATIONAL_ID_LENGTH = 8;

type LookupStatus = "idle" | "checking" | "ready" | "error";

type GlobalBorrowerLookupProps = {
  compact?: boolean;
  forceExpanded?: boolean;
  className?: string;
};

export function GlobalBorrowerLookup({
  compact = false,
  forceExpanded = false,
  className = "",
}: GlobalBorrowerLookupProps) {
  const router = useRouter();
  const { currentCompany, currentBranch } = useAppData();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [nationalId, setNationalId] = useState("");
  const [status, setStatus] = useState<LookupStatus>("idle");
  const [result, setResult] = useState<CompanyClientExistingLoanCheck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [printingHistory, setPrintingHistory] = useState(false);

  const normalizedNationalId = nationalId.trim();

  function updateNationalId(value: string) {
    setNationalId(value);
    setStatus("idle");
    setResult(null);
    setError(null);
  }

  async function runLookup(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setDialogOpen(true);

    if (normalizedNationalId.length < MINIMUM_NATIONAL_ID_LENGTH) {
      setStatus("error");
      setResult(null);
      setError(`Enter at least ${MINIMUM_NATIONAL_ID_LENGTH} national-ID characters.`);
      return;
    }

    setStatus("checking");
    setResult(null);
    setError(null);
    try {
      const response = await checkCompanyClientExistingLoans(normalizedNationalId);
      setResult(response);
      setStatus("ready");
    } catch (lookupError: unknown) {
      setStatus("error");
      setError(getErrorMessage(lookupError, "The borrower history check could not be completed."));
    }
  }

  async function generateAndPrintHistory() {
    if (!result?.borrower_found) return;

    const popup = window.open("", "_blank", "width=1400,height=900");
    if (!popup) {
      toast.error("The print window was blocked. Allow pop-ups for LoanHub and try again.");
      return;
    }

    prepareDocumentGenerationWindow(popup, {
      title: "Preparing borrower history report",
      description: "LoanHub is compiling the permitted aggregate history and the active company borrower record.",
      companyId: currentCompany?.id ?? null,
      companyName: currentCompany?.name ?? "Loan company",
    });

    setPrintingHistory(true);
    try {
      const profile = result.already_company_client && result.company_client_account_id
        ? await getCompanyClientProfile(result.company_client_account_id)
        : null;

      await renderBorrowerHistoryReport(popup, {
        lookup: result,
        profile,
        company: {
          id: currentCompany?.id ?? null,
          name: currentCompany?.name ?? "Loan company",
          licenseNumber: currentCompany?.license_number ?? null,
          phone: currentCompany?.phone ?? null,
          email: currentCompany?.email ?? null,
          address: currentCompany?.address ?? null,
          branchName: currentBranch?.name ?? null,
        },
      });

      toast.success("Borrower history report generated", {
        description: "Use the browser print dialog to print or save the report as PDF.",
      });
    } catch (printError: unknown) {
      markDocumentGenerationFailed(
        popup,
        "The borrower history report could not be prepared. Return to LoanHub and try again.",
      );
      toast.error(getErrorMessage(printError, "The borrower history report could not be generated."));
    } finally {
      setPrintingHistory(false);
    }
  }

  function continueToClients(action: GlobalBorrowerLookupAction) {
    const detail = { action, nationalId: normalizedNationalId } as const;
    const href = borrowerLookupHref(detail);
    setDialogOpen(false);

    if (window.location.pathname === "/company/clients") {
      window.history.replaceState(null, "", href);
      dispatchGlobalBorrowerLookup(detail);
      return;
    }
    router.push(href);
  }

  const compactButton = (
    <Button
      type="button"
      variant="outline"
      size="icon"
      onClick={() => setDialogOpen(true)}
      aria-label="Check borrower history by national ID"
      title="Global national-ID borrower lookup"
      className="h-10 w-10 shrink-0"
    >
      <IdCard className="h-4 w-4" />
    </Button>
  );

  return (
    <>
      {compact ? compactButton : (
        <>
          <form
            onSubmit={(event) => void runLookup(event)}
            className={`${forceExpanded ? "flex flex-1" : "hidden xl:flex"} h-10 min-w-0 items-center rounded-xl border bg-background shadow-sm ${className}`}
            role="search"
            aria-label="Global borrower national-ID lookup"
            data-borrower-lookup-mode={forceExpanded ? "expanded" : "responsive"}
          >
            <IdCard className="ml-3 h-4 w-4 shrink-0 text-muted-foreground" />
            <Input
              value={nationalId}
              onChange={(event) => updateNationalId(event.target.value)}
              placeholder="Check borrower National ID"
              aria-label="Borrower national ID"
              autoComplete="off"
              className={`${forceExpanded ? "min-w-0 flex-1" : "w-56 2xl:w-72"} h-9 border-0 bg-transparent shadow-none focus-visible:ring-0`}
            />
            <Button
              type="submit"
              size="sm"
              className="mr-1 h-8 rounded-lg px-3"
              disabled={status === "checking"}
            >
              {status === "checking" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              Check
            </Button>
          </form>
          {!forceExpanded ? <span className="xl:hidden">{compactButton}</span> : null}
        </>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <IdCard className="h-5 w-5 text-primary" />
              Global borrower history check
            </DialogTitle>
            <DialogDescription>
              Search LoanHub by national ID before opening a borrower account. Only aggregate credit history is shown; other lenders&apos; private notes, documents and company records remain protected.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={(event) => void runLookup(event)} className="space-y-3">
            <Label htmlFor="global-borrower-national-id">National ID</Label>
            <div className="flex gap-2">
              <Input
                id="global-borrower-national-id"
                value={nationalId}
                onChange={(event) => updateNationalId(event.target.value)}
                placeholder="Enter borrower National ID"
                autoComplete="off"
                autoFocus
              />
              <Button type="submit" disabled={status === "checking"}>
                {status === "checking" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                Check history
              </Button>
            </div>
          </form>

          {status === "idle" ? (
            <div className="rounded-2xl border bg-muted/30 p-4 text-sm text-muted-foreground">
              Enter the National ID to find an existing borrower profile and LoanHub loan history. External credit-bureau checks remain a separate consent-controlled process.
            </div>
          ) : null}

          {status === "checking" ? (
            <div role="status" className="flex items-center gap-3 rounded-2xl border border-primary/20 bg-primary/5 p-5">
              <LoaderCircle className="h-6 w-6 animate-spin text-primary" />
              <div>
                <p className="font-black">Checking LoanHub borrower history…</p>
                <p className="text-sm text-muted-foreground">Searching borrower identity, loan status, repayments and outstanding exposure.</p>
              </div>
            </div>
          ) : null}

          {status === "error" ? (
            <div role="alert" className="flex items-start gap-3 rounded-2xl border border-destructive/30 bg-destructive/5 p-5">
              <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
              <div>
                <p className="font-black text-destructive">History check failed</p>
                <p className="mt-1 text-sm text-muted-foreground">{error}</p>
              </div>
            </div>
          ) : null}

          {status === "ready" && result && !result.borrower_found ? (
            <div role="status" className="space-y-4 rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-5">
              <div className="flex items-start gap-3">
                <UserRoundPlus className="mt-0.5 h-6 w-6 shrink-0 text-emerald-600" />
                <div>
                  <p className="font-black">No borrower history found</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    This National ID is not attached to a LoanHub borrower. Start a new borrower registration with the ID already filled in.
                  </p>
                </div>
              </div>
              <Button type="button" onClick={() => continueToClients("new")}>
                <UserRoundPlus className="h-4 w-4" />
                Add new borrower
              </Button>
            </div>
          ) : null}

          {status === "ready" && result?.borrower_found ? (
            <div role="status" className="space-y-5 rounded-2xl border bg-card p-5 shadow-sm">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex items-start gap-3">
                  <ShieldCheck className="mt-0.5 h-6 w-6 shrink-0 text-primary" />
                  <div>
                    <p className="font-black">Existing LoanHub borrower found</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {result.already_company_client
                        ? "This borrower is already linked to the active company."
                        : "The global borrower identity can be linked to the active company after surname and date-of-birth verification."}
                    </p>
                  </div>
                </div>
                <Badge variant={result.defaulted_loan_count > 0 || result.overdue_loan_count > 0 ? "destructive" : "outline"}>
                  {result.defaulted_loan_count > 0
                    ? `${result.defaulted_loan_count} defaulted`
                    : result.overdue_loan_count > 0
                      ? `${result.overdue_loan_count} overdue`
                      : "No adverse status"}
                </Badge>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <HistoryMetric label="All LoanHub loans" value={String(result.total_loan_count)} />
                <HistoryMetric label="Open loans" value={String(result.active_loan_count)} />
                <HistoryMetric label="Completed loans" value={String(result.completed_loan_count)} />
                <HistoryMetric label="Defaulted loans" value={String(result.defaulted_loan_count)} danger={result.defaulted_loan_count > 0} />
                <HistoryMetric label="Overdue loans" value={String(result.overdue_loan_count)} danger={result.overdue_loan_count > 0} />
                <HistoryMetric label="Lending companies" value={String(result.lender_count)} />
                <HistoryMetric label="Outstanding" value={formatMoney(result.loanhub_outstanding_total)} danger={result.loanhub_outstanding_total > 0} />
                <HistoryMetric label="Lifetime borrowed" value={formatMoney(result.lifetime_principal_total)} />
                <HistoryMetric label="Lifetime paid" value={formatMoney(result.lifetime_paid_total)} />
              </div>

              <div className="flex flex-wrap items-center gap-2 rounded-xl bg-muted/40 px-4 py-3 text-sm">
                <CircleCheckBig className="h-4 w-4 text-primary" />
                <span className="font-semibold">Latest LoanHub loan:</span>
                <span className="text-muted-foreground">{result.latest_loan_at ? formatDate(result.latest_loan_at) : "No loan recorded"}</span>
              </div>

              <DialogFooter className="gap-2 sm:justify-start">
                {result.already_company_client ? (
                  <Button type="button" onClick={() => continueToClients("history")}>
                    <History className="h-4 w-4" />
                    Open borrower record
                  </Button>
                ) : (
                  <Button type="button" onClick={() => continueToClients("link")}>
                    <UserRoundPlus className="h-4 w-4" />
                    Link existing borrower
                  </Button>
                )}
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void generateAndPrintHistory()}
                  disabled={printingHistory}
                  aria-label="Generate and print the borrower history report"
                >
                  {printingHistory ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Printer className="h-4 w-4" />}
                  {printingHistory ? "Generating report…" : "Generate & print history"}
                </Button>
                <Button type="button" variant="outline" onClick={() => updateNationalId("")} disabled={printingHistory}>
                  Check another ID
                </Button>
              </DialogFooter>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}

function HistoryMetric({
  label,
  value,
  danger = false,
}: {
  label: string;
  value: string;
  danger?: boolean;
}) {
  return (
    <div className={`rounded-xl border bg-background p-3 ${danger ? "border-destructive/30" : ""}`}>
      <p className="text-[10px] font-black uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <p className={`mt-1 text-lg font-black ${danger ? "text-destructive" : ""}`}>{value}</p>
    </div>
  );
}
