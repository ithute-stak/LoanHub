"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Link2, RefreshCw, ShieldCheck } from "lucide-react";

import { cdasOfficialApi } from "@/api/cdasOfficial";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import type {
  CdasLinkedActionRequestType,
  CdasOfficialMandateEvent,
  CdasOfficialMandateState,
} from "@/types/cdasOfficial";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

function money(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  return `M ${number.toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function titleCase(value?: string | null) {
  return (value || "unknown").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function eventTime(value?: string | null) {
  if (!value) return "Unknown time";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

const TRANSITIONS: Partial<Record<string, Array<{ requestType: CdasLinkedActionRequestType; label: string }>>> = {
  registered: [
    { requestType: 3, label: "Review in CDAS" },
    { requestType: 6, label: "Cancel" },
  ],
  reviewed: [
    { requestType: 4, label: "Approve in CDAS" },
    { requestType: 6, label: "Cancel" },
  ],
  approved: [
    { requestType: 5, label: "Activate in CDAS" },
    { requestType: 6, label: "Cancel" },
  ],
};

export function CdasLoanLifecyclePanel() {
  const [loanId, setLoanId] = useState("");
  const [employeeNo, setEmployeeNo] = useState("");
  const [itemCode, setItemCode] = useState("");
  const [referenceNo, setReferenceNo] = useState("");
  const [loanPolicy, setLoanPolicy] = useState("0");
  const [deductionAmount, setDeductionAmount] = useState("");
  const [principalAmount, setPrincipalAmount] = useState("");
  const [installments, setInstallments] = useState("");
  const [effectiveMonth, setEffectiveMonth] = useState("");
  const [borrowerConsent, setBorrowerConsent] = useState(false);
  const [state, setState] = useState<CdasOfficialMandateState | null>(null);
  const [events, setEvents] = useState<CdasOfficialMandateEvent[]>([]);
  const [eventsLoaded, setEventsLoaded] = useState(false);
  const [loading, setLoading] = useState<string | null>(null);
  const [effectiveDate, setEffectiveDate] = useState("");
  const [settlementReason, setSettlementReason] = useState("2");
  const [reconcileStatus, setReconcileStatus] = useState("5");

  const transitions = useMemo(
    () => TRANSITIONS[String(state?.lifecycle_status || "").toLowerCase()] || [],
    [state?.lifecycle_status],
  );

  const canRetryRegistration = Boolean(
    state
      && !state.requires_reconciliation
      && state.deduction_id === null
      && state.last_error
      && ["registration_pending", "registration_failed"].includes(String(state.lifecycle_status || "").toLowerCase()),
  );

  function hydrateFormFromState(result: CdasOfficialMandateState) {
    if (result.employee_no || result.employee_number) setEmployeeNo(String(result.employee_no || result.employee_number));
    if (result.item_code) setItemCode(result.item_code);
    if (result.reference_no) setReferenceNo(result.reference_no);
    setLoanPolicy(String(result.loan_policy ?? 0));
    if (result.deduction_amount !== null && result.deduction_amount !== undefined) setDeductionAmount(String(result.deduction_amount));
    if (result.principal_amount !== null && result.principal_amount !== undefined) setPrincipalAmount(String(result.principal_amount));
    if (result.total_installment !== null && result.total_installment !== undefined) setInstallments(String(result.total_installment));
    if (result.effective_month) setEffectiveMonth(result.effective_month);
  }

  async function refreshAuditTrail(stateId: string, silent = false) {
    if (!silent) setLoading("audit");
    try {
      const result = await cdasOfficialApi.getDeductionEvents(stateId);
      setEvents(result);
      setEventsLoaded(true);
    } catch (error: unknown) {
      if (!silent) toast.error(getErrorMessage(error, "Could not load the CDAS audit trail."));
    } finally {
      if (!silent) setLoading(null);
    }
  }

  async function lookupLoan() {
    const value = loanId.trim();
    if (!value) {
      toast.error("Enter the LoanHub loan ID first.");
      return;
    }
    setLoading("lookup");
    try {
      const result = await cdasOfficialApi.getLoanDeduction(value);
      setState(result);
      hydrateFormFromState(result);
      await refreshAuditTrail(result.id, true);
      toast.success("Linked CDAS deduction loaded.");
    } catch (error: unknown) {
      setState(null);
      setEvents([]);
      setEventsLoaded(false);
      toast.error(getErrorMessage(error, "No official CDAS deduction could be loaded for this loan."));
    } finally {
      setLoading(null);
    }
  }

  async function register() {
    if (!loanId.trim() || !employeeNo.trim() || !itemCode.trim() || !referenceNo.trim()) {
      toast.error("Loan ID, employee number, item code and reference number are required.");
      return;
    }
    if (!borrowerConsent) {
      toast.error("Borrower consent must be confirmed before CDAS registration.");
      return;
    }
    if (!effectiveMonth.match(/^\d{4}-(0[1-9]|1[0-2])$/)) {
      toast.error("Effective month must use YYYY-MM format.");
      return;
    }
    if (!window.confirm("Register this LoanHub loan as a payroll deduction in CDAS? This is an external state-changing action.")) return;

    setLoading("register");
    try {
      const result = await cdasOfficialApi.registerLoanDeduction({
        loan_id: loanId.trim(),
        employee_no: employeeNo.trim(),
        item_code: itemCode.trim(),
        reference_no: referenceNo.trim(),
        loan_policy: Number(loanPolicy || 0),
        deduction_amount: Number(deductionAmount),
        principal_amount: Number(principalAmount),
        total_installment: Number(installments),
        effective_month: effectiveMonth,
        borrower_consent: borrowerConsent,
      });
      setState(result);
      hydrateFormFromState(result);
      await refreshAuditTrail(result.id, true);
      toast.success("CDAS deduction registered and permanently linked to the LoanHub loan.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "CDAS registration failed."));
      try {
        const existing = await cdasOfficialApi.getLoanDeduction(loanId.trim());
        setState(existing);
        hydrateFormFromState(existing);
        await refreshAuditTrail(existing.id, true);
      } catch {
        // The backend remains authoritative. Do not retry a failed provider write here.
      }
    } finally {
      setLoading(null);
    }
  }

  async function retryRegistration() {
    if (!state || !canRetryRegistration) return;
    if (!itemCode.trim() || !referenceNo.trim()) {
      toast.error("Item code and reference number are required.");
      return;
    }
    if (!effectiveMonth.match(/^\d{4}-(0[1-9]|1[0-2])$/)) {
      toast.error("Effective month must use YYYY-MM format.");
      return;
    }
    if (!window.confirm("Retry this rejected CDAS registration with the corrected values? LoanHub will only send it if the previous provider rejection is confirmed retry-safe.")) return;

    setLoading("retry-register");
    try {
      const result = await cdasOfficialApi.retryLoanDeductionRegistration(state.id, {
        item_code: itemCode.trim(),
        reference_no: referenceNo.trim(),
        loan_policy: Number(loanPolicy || 0),
        deduction_amount: Number(deductionAmount),
        principal_amount: Number(principalAmount),
        total_installment: Number(installments),
        effective_month: effectiveMonth,
      });
      setState(result);
      hydrateFormFromState(result);
      await refreshAuditTrail(result.id, true);
      toast.success("Corrected CDAS registration completed.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "CDAS registration retry failed."));
      try {
        const refreshed = await cdasOfficialApi.getDeductionState(state.id);
        setState(refreshed);
        hydrateFormFromState(refreshed);
        await refreshAuditTrail(refreshed.id, true);
      } catch {
        // Never replay a retry automatically.
      }
    } finally {
      setLoading(null);
    }
  }

  async function runAction(requestType: CdasLinkedActionRequestType, label: string) {
    if (!state) return;
    if (!window.confirm(`${label}? This changes the linked deduction in CDAS and will be recorded in the audit trail.`)) return;
    setLoading(`action-${requestType}`);
    try {
      const result = await cdasOfficialApi.runDeductionAction(state.id, { request_type: requestType });
      setState(result);
      await refreshAuditTrail(result.id, true);
      toast.success(`${label} completed.`);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, `${label} failed.`));
      try {
        const refreshed = await cdasOfficialApi.getDeductionState(state.id);
        setState(refreshed);
        await refreshAuditTrail(refreshed.id, true);
      } catch {
        // Never auto-replay a CDAS write.
      }
    } finally {
      setLoading(null);
    }
  }

  async function modifyActive() {
    if (!state || !effectiveDate.trim()) {
      toast.error("Enter the effective date for the active-deduction change.");
      return;
    }
    if (!window.confirm("Modify this active CDAS deduction? The request will not be automatically replayed if the provider response is uncertain.")) return;
    setLoading("modify");
    try {
      const result = await cdasOfficialApi.modifyActiveDeduction(state.id, { effective_date: effectiveDate.trim() });
      setState(result);
      await refreshAuditTrail(result.id, true);
      toast.success("Active CDAS deduction updated.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "CDAS modification failed."));
      try {
        const refreshed = await cdasOfficialApi.getDeductionState(state.id);
        setState(refreshed);
        await refreshAuditTrail(refreshed.id, true);
      } catch {
        // Never auto-replay a CDAS write.
      }
    } finally {
      setLoading(null);
    }
  }

  async function settle() {
    if (!state || !effectiveDate.trim()) {
      toast.error("Enter the settlement effective date.");
      return;
    }
    const reason = Number(settlementReason);
    if (![1, 2, 3, 4].includes(reason)) {
      toast.error("Select a valid CDAS settlement reason.");
      return;
    }
    if (!window.confirm("Settle this payroll deduction in CDAS? Confirm only after verifying the loan settlement in LoanHub.")) return;
    setLoading("settle");
    try {
      const result = await cdasOfficialApi.settleDeduction(state.id, {
        effective_date: effectiveDate.trim(),
        settlement_reason: reason as 1 | 2 | 3 | 4,
      });
      setState(result);
      await refreshAuditTrail(result.id, true);
      toast.success("CDAS deduction settled.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "CDAS settlement failed."));
      try {
        const refreshed = await cdasOfficialApi.getDeductionState(state.id);
        setState(refreshed);
        await refreshAuditTrail(refreshed.id, true);
      } catch {
        // Never auto-replay a CDAS write.
      }
    } finally {
      setLoading(null);
    }
  }

  async function reconcile() {
    if (!state) return;
    const status = Number(reconcileStatus);
    if (!Number.isInteger(status) || status < 1 || status > 10) {
      toast.error("Reconciliation status must be a CDAS status code from 1 to 10.");
      return;
    }
    setLoading("reconcile");
    try {
      const result = await cdasOfficialApi.reconcileDeduction(state.id, status);
      setState(result);
      await refreshAuditTrail(result.id, true);
      toast.success("CDAS state reconciled from the provider.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "CDAS reconciliation failed."));
    } finally {
      setLoading(null);
    }
  }

  const isActive = ["active", "changed"].includes(String(state?.lifecycle_status || "").toLowerCase());

  return (
    <div className="space-y-5">
      <Alert>
        <ShieldCheck className="h-4 w-4" />
        <AlertTitle>Loan-linked CDAS lifecycle</AlertTitle>
        <AlertDescription>
          Every provider write is tied to a real LoanHub loan and stored in the CDAS lifecycle audit ledger. Write requests are never silently retried after an uncertain provider response.
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle>Find an existing loan deduction</CardTitle>
          <CardDescription>Enter the LoanHub loan UUID. This lookup is explicit and does not run automatically on page load.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row">
          <Input value={loanId} onChange={(event) => setLoanId(event.target.value)} placeholder="LoanHub loan ID" autoComplete="off" />
          <LoadingButton loading={loading === "lookup"} loadingText="Loading..." onClick={lookupLoan} variant="outline">
            <Link2 className="h-4 w-4" />Load linked deduction
          </LoadingButton>
        </CardContent>
      </Card>

      {!state && (
        <Card>
          <CardHeader>
            <CardTitle>Register approved loan in CDAS</CardTitle>
            <CardDescription>Use only after the LoanHub loan, employee details, affordability and borrower consent have been verified.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              <div className="space-y-2"><Label>Employee number</Label><Input value={employeeNo} onChange={(e) => setEmployeeNo(e.target.value)} /></div>
              <div className="space-y-2"><Label>CDAS item code</Label><Input value={itemCode} onChange={(e) => setItemCode(e.target.value)} /></div>
              <div className="space-y-2"><Label>Reference number</Label><Input value={referenceNo} onChange={(e) => setReferenceNo(e.target.value)} /></div>
              <div className="space-y-2"><Label>Loan policy</Label><Input type="number" min={0} value={loanPolicy} onChange={(e) => setLoanPolicy(e.target.value)} /></div>
              <div className="space-y-2"><Label>Monthly deduction</Label><Input type="number" min="0.01" step="0.01" value={deductionAmount} onChange={(e) => setDeductionAmount(e.target.value)} /></div>
              <div className="space-y-2"><Label>Principal amount</Label><Input type="number" min="0.01" step="0.01" value={principalAmount} onChange={(e) => setPrincipalAmount(e.target.value)} /></div>
              <div className="space-y-2"><Label>Total installments</Label><Input type="number" min={1} max={600} value={installments} onChange={(e) => setInstallments(e.target.value)} /></div>
              <div className="space-y-2"><Label>Effective month</Label><Input type="month" value={effectiveMonth} onChange={(e) => setEffectiveMonth(e.target.value)} /></div>
            </div>
            <div className="flex items-start gap-3 rounded-lg border p-4">
              <Checkbox id="borrower-consent" checked={borrowerConsent} onCheckedChange={(value) => setBorrowerConsent(value === true)} />
              <div>
                <Label htmlFor="borrower-consent">Borrower consent confirmed</Label>
                <p className="mt-1 text-xs text-muted-foreground">Required before LoanHub can register a payroll deduction with CDAS.</p>
              </div>
            </div>
            <LoadingButton loading={loading === "register"} loadingText="Registering in CDAS..." onClick={register}>
              <CheckCircle2 className="h-4 w-4" />Register and link deduction
            </LoadingButton>
          </CardContent>
        </Card>
      )}

      {state && (
        <>
          {state.requires_reconciliation && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Provider result requires reconciliation</AlertTitle>
              <AlertDescription>
                LoanHub will not retry the previous write. Read the current deduction status from CDAS using the reconciliation control below before attempting another change.
              </AlertDescription>
            </Alert>
          )}

          {canRetryRegistration && (
            <Card>
              <CardHeader>
                <CardTitle>Correct rejected registration</CardTitle>
                <CardDescription>
                  CDAS returned a confirmed rejection, so these values can be corrected and explicitly resubmitted. The employee and LoanHub loan remain fixed.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>Previous CDAS rejection</AlertTitle>
                  <AlertDescription>{state.last_error}</AlertDescription>
                </Alert>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  <div className="space-y-2"><Label>Employee number</Label><Input value={employeeNo} disabled /></div>
                  <div className="space-y-2"><Label>CDAS item code</Label><Input value={itemCode} onChange={(e) => setItemCode(e.target.value)} /></div>
                  <div className="space-y-2"><Label>Reference number</Label><Input value={referenceNo} onChange={(e) => setReferenceNo(e.target.value)} /></div>
                  <div className="space-y-2"><Label>Loan policy</Label><Input type="number" min={0} value={loanPolicy} onChange={(e) => setLoanPolicy(e.target.value)} /></div>
                  <div className="space-y-2"><Label>Monthly deduction</Label><Input type="number" min="0.01" step="0.01" value={deductionAmount} onChange={(e) => setDeductionAmount(e.target.value)} /></div>
                  <div className="space-y-2"><Label>Principal amount</Label><Input type="number" min="0.01" step="0.01" value={principalAmount} onChange={(e) => setPrincipalAmount(e.target.value)} /></div>
                  <div className="space-y-2"><Label>Total installments</Label><Input type="number" min={1} max={600} value={installments} onChange={(e) => setInstallments(e.target.value)} /></div>
                  <div className="space-y-2"><Label>Effective month</Label><Input type="month" value={effectiveMonth} onChange={(e) => setEffectiveMonth(e.target.value)} /></div>
                </div>
                <LoadingButton loading={loading === "retry-register"} loadingText="Retrying registration..." disabled={Boolean(loading)} onClick={retryRegistration}>
                  <RefreshCw className="h-4 w-4" />Correct and retry registration
                </LoadingButton>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <CardTitle>Official linked deduction</CardTitle>
                  <CardDescription>Loan {String(state.loan_id || loanId || "—")}</CardDescription>
                </div>
                <div className="flex gap-2">
                  <Badge variant={state.environment === "live" ? "default" : "secondary"}>{String(state.environment).toUpperCase()}</Badge>
                  <Badge variant="outline">{titleCase(state.lifecycle_status)}</Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
                <div><div className="text-muted-foreground">Employee</div><div className="font-medium">{String(state.employee_no || state.employee_number || "—")}</div></div>
                <div><div className="text-muted-foreground">CDAS deduction ID</div><div className="font-medium">{state.deduction_id ?? "Pending"}</div></div>
                <div><div className="text-muted-foreground">Item code</div><div className="font-medium">{state.item_code}</div></div>
                <div><div className="text-muted-foreground">Reference</div><div className="font-medium">{state.reference_no}</div></div>
                <div><div className="text-muted-foreground">Principal</div><div className="font-medium">{money(state.principal_amount)}</div></div>
                <div><div className="text-muted-foreground">Deduction</div><div className="font-medium">{money(state.deduction_amount)}</div></div>
                <div><div className="text-muted-foreground">Effective month</div><div className="font-medium">{state.effective_month || "—"}</div></div>
                <div><div className="text-muted-foreground">CDAS status code</div><div className="font-medium">{state.cdas_status ?? "—"}</div></div>
              </div>

              {state.last_error && !canRetryRegistration && <Alert variant="destructive"><AlertTitle>Last provider error</AlertTitle><AlertDescription>{state.last_error}</AlertDescription></Alert>}

              {!state.requires_reconciliation && transitions.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {transitions.map((action) => (
                    <LoadingButton
                      key={action.requestType}
                      variant={action.requestType === 6 ? "outline" : "default"}
                      loading={loading === `action-${action.requestType}`}
                      loadingText="Sending..."
                      disabled={Boolean(loading)}
                      onClick={() => runAction(action.requestType, action.label)}
                    >
                      {action.label}
                    </LoadingButton>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {(state.requires_reconciliation || isActive) && (
            <Card>
              <CardHeader>
                <CardTitle>{state.requires_reconciliation ? "Reconcile uncertain state" : "Active deduction controls"}</CardTitle>
                <CardDescription>These actions are explicit because they read from or change the external CDAS system.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {state.requires_reconciliation && (
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                    <div className="space-y-2"><Label>CDAS status to query</Label><Input type="number" min={1} max={10} value={reconcileStatus} onChange={(e) => setReconcileStatus(e.target.value)} /></div>
                    <LoadingButton loading={loading === "reconcile"} loadingText="Reconciling..." onClick={reconcile} variant="outline"><RefreshCw className="h-4 w-4" />Reconcile from CDAS</LoadingButton>
                  </div>
                )}

                {isActive && !state.requires_reconciliation && (
                  <>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-2"><Label>Effective date</Label><Input type="date" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} /></div>
                      <div className="space-y-2">
                        <Label>Settlement reason</Label>
                        <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={settlementReason} onChange={(e) => setSettlementReason(e.target.value)}>
                          <option value="1">Policy expired</option>
                          <option value="2">Paid by employee</option>
                          <option value="3">Consolidation</option>
                          <option value="4">Deceased employee</option>
                        </select>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <LoadingButton loading={loading === "modify"} loadingText="Updating..." disabled={Boolean(loading)} onClick={modifyActive} variant="outline">Modify active deduction</LoadingButton>
                      <LoadingButton loading={loading === "settle"} loadingText="Settling..." disabled={Boolean(loading)} onClick={settle}>Settle deduction</LoadingButton>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <CardTitle>CDAS lifecycle audit trail</CardTitle>
                  <CardDescription>Local append-only history of provider writes and reconciliation activity for this mandate.</CardDescription>
                </div>
                <Button variant="outline" size="sm" disabled={loading === "audit"} onClick={() => refreshAuditTrail(state.id)}>
                  <RefreshCw className={loading === "audit" ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
                  Refresh audit
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {!eventsLoaded ? (
                <p className="text-sm text-muted-foreground">Audit history has not been loaded yet.</p>
              ) : events.length === 0 ? (
                <p className="text-sm text-muted-foreground">No lifecycle events have been recorded yet.</p>
              ) : (
                <div className="space-y-3">
                  {events.map((event) => (
                    <div key={event.id} className="rounded-lg border p-3">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <div className="font-medium">{titleCase(event.event_type)}</div>
                          <div className="mt-1 text-xs text-muted-foreground">{eventTime(event.occurred_at)}</div>
                        </div>
                        <Badge variant={event.success ? "secondary" : "destructive"}>{event.success ? "Success" : "Failed"}</Badge>
                      </div>
                      <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-3">
                        <div>Request type: <span className="text-foreground">{event.request_type ?? "—"}</span></div>
                        <div>Provider status: <span className="text-foreground">{event.provider_status_code ?? "—"}</span></div>
                        <div>Actor: <span className="break-all text-foreground">{event.actor_user_id ?? "System"}</span></div>
                      </div>
                      {event.message && <div className="mt-2 text-sm">{event.message}</div>}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
