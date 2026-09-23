"use client";

import Link from "next/link";
import { useState } from "react";
import {
  BadgeCheck,
  CalendarClock,
  Landmark,
  ReceiptText,
  ShieldCheck,
  UserRoundSearch,
  WalletCards,
} from "lucide-react";

import { cdasOfficialApi } from "@/api/cdasOfficial";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import type { CdasBorrowerIntelligenceResponse } from "@/types/cdasOfficial";
import { getErrorMessage } from "@/utils/apiError";

const money = new Intl.NumberFormat("en-LS", {
  style: "currency",
  currency: "LSL",
  minimumFractionDigits: 2,
});

export default function CdasBorrowerIntelligencePage() {
  const [nationalId, setNationalId] = useState("");
  const [employeeNo, setEmployeeNo] = useState("");
  const [ownStatus, setOwnStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<CdasBorrowerIntelligenceResponse | null>(null);

  async function runIntelligence() {
    const id = nationalId.trim();
    const employee = employeeNo.trim();
    if (!id || !employee) {
      setError("Enter both the LoanHub client National ID and the CDAS employee number.");
      return;
    }

    const parsedStatus = ownStatus.trim() ? Number(ownStatus.trim()) : undefined;
    if (parsedStatus !== undefined && (!Number.isInteger(parsedStatus) || parsedStatus < 1 || parsedStatus > 10)) {
      setError("Own deduction status must be a whole number from 1 to 10.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);
    try {
      const response = await cdasOfficialApi.runBorrowerIntelligence({
        national_id: id,
        employee_no: employee,
        own_deduction_status: parsedStatus,
      });
      setResult(response);
    } catch (requestError: unknown) {
      setError(getErrorMessage(requestError, "Borrower intelligence check failed."));
    } finally {
      setLoading(false);
    }
  }

  const proposal = result?.loanhub.collection_proposal;

  return (
    <div className="space-y-6 pb-10">
      <div>
        <div className="flex items-center gap-2">
          <UserRoundSearch className="h-6 w-6" />
          <h1 className="text-2xl font-semibold tracking-tight">CDAS Borrower Intelligence</h1>
        </div>
        <p className="mt-1 max-w-4xl text-sm text-muted-foreground">
          Match one LoanHub client by National ID, read the employee from official CDAS, and combine live payroll capacity with the client&apos;s current LoanHub balances.
        </p>
      </div>

      <Alert>
        <ShieldCheck className="h-4 w-4" />
        <AlertTitle>Exact identifiers only</AlertTitle>
        <AlertDescription>
          LoanHub resolves the client by exact normalized National ID and CDAS must return the exact employee number searched. Names and date of birth are never used as a fuzzy automatic fallback. CDAS v1.5 does not document National ID in Employee Details; if CDAS supplies one, it must also match exactly.
        </AlertDescription>
      </Alert>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Intelligence check failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Identify the client</CardTitle>
          <CardDescription>
            National ID identifies the LoanHub client. Employee number identifies the same client in CDAS payroll.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="national-id">National ID</Label>
              <Input
                id="national-id"
                value={nationalId}
                onChange={(event) => setNationalId(event.target.value)}
                placeholder="Client National ID"
                autoComplete="off"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="employee-no">CDAS employee number</Label>
              <Input
                id="employee-no"
                value={employeeNo}
                onChange={(event) => setEmployeeNo(event.target.value)}
                placeholder="EmployeeNo"
                autoComplete="off"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="own-status">Our deduction status (optional)</Label>
              <Input
                id="own-status"
                value={ownStatus}
                onChange={(event) => setOwnStatus(event.target.value)}
                placeholder="e.g. 5 = Active"
                inputMode="numeric"
                autoComplete="off"
              />
            </div>
          </div>
          <LoadingButton loading={loading} loadingText="Checking LoanHub + CDAS..." onClick={runIntelligence}>
            <UserRoundSearch className="h-4 w-4" />Run borrower intelligence
          </LoadingButton>
        </CardContent>
      </Card>

      {result && proposal && (
        <>
          <Card className="border-emerald-500/40">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BadgeCheck className="h-5 w-5" />Exact client link verified
              </CardTitle>
              <CardDescription>
                {result.identity.client_name || result.snapshot.profile.full_name || "LoanHub client"} · National ID {result.identity.national_id_masked} · CDAS employee {result.identity.employee_no}
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <div><div className="text-muted-foreground">LoanHub account</div><div className="font-medium">{result.identity.account_reference}</div></div>
              <div><div className="text-muted-foreground">Identity basis</div><div className="font-medium">Exact National ID + Employee No.</div></div>
              <div><div className="text-muted-foreground">CDAS department</div><div className="font-medium">{result.snapshot.profile.department || "—"}</div></div>
              <div><div className="text-muted-foreground">Provider National ID</div><div className="font-medium">{result.identity.provider_national_id_present ? "Returned and matched" : "Not provided by v1.5 response"}</div></div>
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Card>
              <CardHeader className="pb-2"><CardDescription>LoanHub amount owing</CardDescription><CardTitle>{money.format(result.loanhub.total_outstanding)}</CardTitle></CardHeader>
              <CardContent className="text-xs text-muted-foreground">Active/defaulted positive balances only</CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2"><CardDescription>CDAS available affordability</CardDescription><CardTitle>{money.format(proposal.available_affordability)}</CardTitle></CardHeader>
              <CardContent className="text-xs text-muted-foreground">Live official CDAS response</CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2"><CardDescription>Suggested collection deduction</CardDescription><CardTitle>{money.format(proposal.suggested_monthly_deduction)}</CardTitle></CardHeader>
              <CardContent className="text-xs text-muted-foreground">Capped at current amount owing</CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2"><CardDescription>Estimated collection period</CardDescription><CardTitle>{proposal.estimated_collection_months ? `${proposal.estimated_collection_months} month${proposal.estimated_collection_months === 1 ? "" : "s"}` : "—"}</CardTitle></CardHeader>
              <CardContent className="text-xs text-muted-foreground">Simple current balance ÷ current CDAS capacity</CardContent>
            </Card>
          </div>

          <Alert variant={proposal.can_add_deduction ? "default" : undefined}>
            <WalletCards className="h-4 w-4" />
            <AlertTitle>{proposal.can_add_deduction ? "Payroll collection capacity detected" : "No additional collection capacity detected"}</AlertTitle>
            <AlertDescription>
              {proposal.can_add_deduction
                ? `LoanHub currently sees ${money.format(proposal.total_outstanding)} owing and CDAS reports ${money.format(proposal.available_affordability)} available. The current collection proposal is ${money.format(proposal.suggested_monthly_deduction)} per month.`
                : `LoanHub will not propose a new payroll deduction because either the current LoanHub balance or current CDAS affordability is zero.`}
              {" "}{proposal.warning}
            </AlertDescription>
          </Alert>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><ReceiptText className="h-5 w-5" />LoanHub obligations</CardTitle>
              <CardDescription>
                The client&apos;s approved, active and defaulted loans in this company. Only active/defaulted positive balances are counted as currently owing.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {result.loanhub.loans.length === 0 ? (
                <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">No qualifying LoanHub loans found for this client.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="border-b text-left text-muted-foreground">
                      <tr>
                        <th className="py-3 pr-4 font-medium">Loan</th>
                        <th className="py-3 pr-4 font-medium">Status</th>
                        <th className="py-3 pr-4 font-medium">Balance</th>
                        <th className="py-3 pr-4 font-medium">Installment</th>
                        <th className="py-3 pr-4 font-medium">Paid</th>
                        <th className="py-3 font-medium">Maturity</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.loanhub.loans.map((loan) => (
                        <tr key={loan.loan_id} className="border-b last:border-0">
                          <td className="py-3 pr-4 font-medium">{loan.loan_reference}</td>
                          <td className="py-3 pr-4 capitalize">{loan.status.replaceAll("_", " ")}</td>
                          <td className="py-3 pr-4">{money.format(loan.balance)}</td>
                          <td className="py-3 pr-4">{money.format(loan.installment_amount)}</td>
                          <td className="py-3 pr-4">{money.format(loan.amount_paid)}</td>
                          <td className="py-3">{loan.maturity_date || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Landmark className="h-5 w-5" />CDAS payroll position</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 text-sm sm:grid-cols-2">
                <div><div className="text-muted-foreground">Employee</div><div className="font-medium">{result.snapshot.profile.full_name || result.identity.employee_no}</div></div>
                <div><div className="text-muted-foreground">Current active deductions</div><div className="font-medium">{money.format(result.snapshot.reported_active_monthly_deductions)}</div></div>
                <div><div className="text-muted-foreground">All returned monthly deductions</div><div className="font-medium">{money.format(result.snapshot.total_monthly_deductions)}</div></div>
                <div><div className="text-muted-foreground">CDAS capacity status</div><div className="font-medium">{result.snapshot.capacity.status.replaceAll("_", " ")}</div></div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><CalendarClock className="h-5 w-5" />Next controlled action</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <p>
                  This screen does not change a payroll deduction. Registration or modification stays inside the official loan lifecycle where LoanHub checks the approved loan terms, borrower consent, user role and reconciliation state.
                </p>
                <Button asChild disabled={!proposal.can_add_deduction}>
                  <Link href="/company/cdas-booking/lifecycle">Open Official Loan Lifecycle</Link>
                </Button>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
