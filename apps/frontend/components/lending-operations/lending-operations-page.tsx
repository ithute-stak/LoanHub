"use client";

import {
  AlertTriangle,
  BadgeCheck,
  BanknoteArrowDown,
  BookOpenCheck,
  BriefcaseBusiness,
  CheckCircle2,
  ClipboardCheck,
  FileChartColumn,
  GitBranch,
  HandCoins,
  Landmark,
  Loader2,
  Plus,
  RefreshCcw,
  Scale,
  SearchCheck,
  ShieldAlert,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { listCompanyClients } from "@/api/companyClients";
import { lendingOperationsApi } from "@/api/lendingOperations";
import { listLoans } from "@/api/loans";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { SearchableCombobox } from "@/components/ui/searchable-combobox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { formatDate, formatDateTime, formatMoney, titleCase } from "@/lib/format";
import type { CompanyClient } from "@/types/companyClient";
import type {
  CDASAffordability,
  CDASMandate,
  CDASPayrollProfile,
  CDASRemittanceBatch,
  CollectionCase,
  ComplianceCase,
  CreditBureauEnquiry,
  CreditDecision,
  CreditDecisionPolicy,
  LendingOperationsDashboard,
  ReconciliationException,
  ReconciliationRun,
  RegulatorySubmission,
  WorkflowInstance,
  WorkflowTemplate,
} from "@/types/lendingOperations";
import type { Loan } from "@/types/loan";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type WorkspaceTab =
  | "cdas"
  | "reconciliation"
  | "credit-bureau"
  | "compliance"
  | "collections"
  | "regulatory"
  | "decisions";

const today = new Date().toISOString().slice(0, 10);
const yearStart = `${new Date().getFullYear()}-01-01`;

export function LendingOperationsPage() {
  const [tab, setTab] = useState<WorkspaceTab>("cdas");
  const [dashboard, setDashboard] = useState<LendingOperationsDashboard | null>(null);
  const [clients, setClients] = useState<CompanyClient[]>([]);
  const [loans, setLoans] = useState<Loan[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [loadedTabs, setLoadedTabs] = useState<Set<WorkspaceTab>>(new Set());

  const [payrollProfiles, setPayrollProfiles] = useState<CDASPayrollProfile[]>([]);
  const [mandates, setMandates] = useState<CDASMandate[]>([]);
  const [batches, setBatches] = useState<CDASRemittanceBatch[]>([]);
  const [affordability, setAffordability] = useState<CDASAffordability | null>(null);
  const [runs, setRuns] = useState<ReconciliationRun[]>([]);
  const [exceptions, setExceptions] = useState<ReconciliationException[]>([]);
  const [enquiries, setEnquiries] = useState<CreditBureauEnquiry[]>([]);
  const [complianceCases, setComplianceCases] = useState<ComplianceCase[]>([]);
  const [collectionCases, setCollectionCases] = useState<CollectionCase[]>([]);
  const [submissions, setSubmissions] = useState<RegulatorySubmission[]>([]);
  const [policies, setPolicies] = useState<CreditDecisionPolicy[]>([]);
  const [decisions, setDecisions] = useState<CreditDecision[]>([]);
  const [workflowTemplates, setWorkflowTemplates] = useState<WorkflowTemplate[]>([]);
  const [workflowInstances, setWorkflowInstances] = useState<WorkflowInstance[]>([]);

  const refreshDashboard = useCallback(async () => {
    setDashboard(await lendingOperationsApi.dashboard());
  }, []);

  const loadTab = useCallback(async (nextTab: WorkspaceTab, force = false) => {
    if (!force && loadedTabs.has(nextTab)) return;
    setLoading(true);
    try {
      if (nextTab === "cdas") {
        const [profiles, mandateRows, batchRows] = await Promise.all([
          lendingOperationsApi.listPayrollProfiles(),
          lendingOperationsApi.listCDASMandates(),
          lendingOperationsApi.listCDASBatches(),
        ]);
        setPayrollProfiles(profiles);
        setMandates(mandateRows);
        setBatches(batchRows);
      } else if (nextTab === "reconciliation") {
        const [runRows, exceptionRows] = await Promise.all([
          lendingOperationsApi.listReconciliationRuns(),
          lendingOperationsApi.listReconciliationExceptions(),
        ]);
        setRuns(runRows);
        setExceptions(exceptionRows);
      } else if (nextTab === "credit-bureau") {
        setEnquiries(await lendingOperationsApi.listCreditEnquiries());
      } else if (nextTab === "compliance") {
        setComplianceCases(await lendingOperationsApi.listComplianceCases());
      } else if (nextTab === "collections") {
        setCollectionCases(await lendingOperationsApi.listCollectionCases());
      } else if (nextTab === "regulatory") {
        setSubmissions(await lendingOperationsApi.listRegulatorySubmissions());
      } else {
        const [policyRows, decisionRows, templates, instances] = await Promise.all([
          lendingOperationsApi.listDecisionPolicies(),
          lendingOperationsApi.listDecisions(),
          lendingOperationsApi.listWorkflowTemplates(),
          lendingOperationsApi.listWorkflowInstances(),
        ]);
        setPolicies(policyRows);
        setDecisions(decisionRows);
        setWorkflowTemplates(templates);
        setWorkflowInstances(instances);
      }
      setLoadedTabs((current) => new Set(current).add(nextTab));
    } catch (error) {
      toast.error(getErrorMessage(error, "The lending-operations module could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [loadedTabs]);

  useEffect(() => {
    void (async () => {
      setLoading(true);
      try {
        const [summary, clientRows, loanRows] = await Promise.all([
          lendingOperationsApi.dashboard(),
          listCompanyClients(),
          listLoans(),
        ]);
        setDashboard(summary);
        setClients(clientRows);
        setLoans(loanRows);
        await loadTab("cdas", true);
      } catch (error) {
        toast.error(getErrorMessage(error, "Lending operations could not be initialised."));
      } finally {
        setLoading(false);
      }
    })();
  // loadTab is intentionally excluded from initial boot to avoid repeated requests.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function refreshCurrent() {
    setLoadedTabs((current) => {
      const next = new Set(current);
      next.delete(tab);
      return next;
    });
    await Promise.all([refreshDashboard(), loadTab(tab, true)]);
  }

  const clientOptions = useMemo(() => clients.map((client) => ({
    value: client.borrower_id,
    label: client.full_name,
    description: `${client.phone}${client.national_id ? ` · ID ${client.national_id}` : ""}`,
    keywords: [client.phone, client.email ?? "", client.national_id ?? "", client.account_reference],
  })), [clients]);

  const loanOptions = useMemo(() => loans.map((loan) => ({
    value: loan.id,
    label: loan.loan_reference,
    description: `${formatMoney(loan.balance)} outstanding · ${titleCase(loan.status)}`,
    keywords: [loan.borrower_id, loan.status],
  })), [loans]);

  return (
    <div className="space-y-5">
      <section className="rounded-[2rem] border bg-gradient-to-br from-primary/10 via-card to-emerald-500/5 p-5 shadow-sm sm:p-7">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-4xl">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border bg-background/80 px-3 py-1 text-xs font-black uppercase tracking-[0.18em] text-primary">
              <Landmark className="h-4 w-4" /> Lending operating system
            </div>
            <h1 className="text-3xl font-black tracking-tight sm:text-4xl">Risk, payroll, compliance and recoveries</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground sm:text-base">
              Manage CDAS salary deductions, reconciliation, bureau checks, KYC/AML/fraud, collections, regulatory returns and automated credit decisions from one controlled workspace.
            </p>
          </div>
          <Button onClick={() => void refreshCurrent()} disabled={loading || working} className="rounded-xl">
            <RefreshCcw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} /> Refresh workspace
          </Button>
        </div>
      </section>

      <SummaryMetrics dashboard={dashboard} />

      {dashboard?.alerts.map((alert) => (
        <div key={alert.message} className="flex items-start gap-3 rounded-2xl border border-red-300 bg-red-50 p-4 text-red-800 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
          <p className="text-sm font-bold">{alert.message}</p>
        </div>
      ))}

      <Tabs value={tab} onValueChange={(value) => { const next = value as WorkspaceTab; setTab(next); void loadTab(next); }}>
        <div className="overflow-x-auto rounded-2xl border bg-card p-2">
          <TabsList className="h-auto min-w-max gap-1 bg-transparent">
            <ModuleTab value="cdas" icon={BanknoteArrowDown} label="CDAS payroll" />
            <ModuleTab value="reconciliation" icon={Scale} label="Reconciliation" />
            <ModuleTab value="credit-bureau" icon={SearchCheck} label="Credit bureau" />
            <ModuleTab value="compliance" icon={ShieldCheck} label="KYC, AML & fraud" />
            <ModuleTab value="collections" icon={HandCoins} label="Collections" />
            <ModuleTab value="regulatory" icon={FileChartColumn} label="Regulatory" />
            <ModuleTab value="decisions" icon={Workflow} label="Decisions & workflows" />
          </TabsList>
        </div>

        {loading ? <LoadingPanel /> : null}

        <TabsContent value="cdas" className="space-y-5">
          <CDASWorkspace
            clients={clients}
            loans={loans}
            clientOptions={clientOptions}
            loanOptions={loanOptions}
            profiles={payrollProfiles}
            mandates={mandates}
            batches={batches}
            affordability={affordability}
            setAffordability={setAffordability}
            working={working}
            runAction={async (action) => {
              setWorking(true);
              try { await action(); await Promise.all([refreshDashboard(), loadTab("cdas", true)]); }
              catch (error) { toast.error(getErrorMessage(error, "CDAS action failed.")); }
              finally { setWorking(false); }
            }}
          />
        </TabsContent>

        <TabsContent value="reconciliation" className="space-y-5">
          <ReconciliationWorkspace
            runs={runs}
            exceptions={exceptions}
            working={working}
            runAction={async (action) => {
              setWorking(true);
              try { await action(); await Promise.all([refreshDashboard(), loadTab("reconciliation", true)]); }
              catch (error) { toast.error(getErrorMessage(error, "Reconciliation action failed.")); }
              finally { setWorking(false); }
            }}
          />
        </TabsContent>

        <TabsContent value="credit-bureau" className="space-y-5">
          <CreditBureauWorkspace
            clients={clients}
            clientOptions={clientOptions}
            enquiries={enquiries}
            working={working}
            runAction={async (action) => {
              setWorking(true);
              try { await action(); await Promise.all([refreshDashboard(), loadTab("credit-bureau", true)]); }
              catch (error) { toast.error(getErrorMessage(error, "Credit-bureau action failed.")); }
              finally { setWorking(false); }
            }}
          />
        </TabsContent>

        <TabsContent value="compliance" className="space-y-5">
          <ComplianceWorkspace
            clientOptions={clientOptions}
            cases={complianceCases}
            working={working}
            runAction={async (action) => {
              setWorking(true);
              try { await action(); await Promise.all([refreshDashboard(), loadTab("compliance", true)]); }
              catch (error) { toast.error(getErrorMessage(error, "Compliance action failed.")); }
              finally { setWorking(false); }
            }}
          />
        </TabsContent>

        <TabsContent value="collections" className="space-y-5">
          <CollectionsWorkspace
            loans={loans}
            loanOptions={loanOptions}
            cases={collectionCases}
            working={working}
            runAction={async (action) => {
              setWorking(true);
              try { await action(); await Promise.all([refreshDashboard(), loadTab("collections", true)]); }
              catch (error) { toast.error(getErrorMessage(error, "Collections action failed.")); }
              finally { setWorking(false); }
            }}
          />
        </TabsContent>

        <TabsContent value="regulatory" className="space-y-5">
          <RegulatoryWorkspace
            submissions={submissions}
            working={working}
            runAction={async (action) => {
              setWorking(true);
              try { await action(); await Promise.all([refreshDashboard(), loadTab("regulatory", true)]); }
              catch (error) { toast.error(getErrorMessage(error, "Regulatory action failed.")); }
              finally { setWorking(false); }
            }}
          />
        </TabsContent>

        <TabsContent value="decisions" className="space-y-5">
          <DecisionWorkspace
            clientOptions={clientOptions}
            loanOptions={loanOptions}
            policies={policies}
            decisions={decisions}
            templates={workflowTemplates}
            instances={workflowInstances}
            working={working}
            runAction={async (action) => {
              setWorking(true);
              try { await action(); await Promise.all([refreshDashboard(), loadTab("decisions", true)]); }
              catch (error) { toast.error(getErrorMessage(error, "Decision/workflow action failed.")); }
              finally { setWorking(false); }
            }}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function SummaryMetrics({ dashboard }: { dashboard: LendingOperationsDashboard | null }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {(dashboard?.metrics ?? []).map((metric) => (
        <Card key={metric.key} className="rounded-2xl">
          <CardContent className="pt-1">
            <p className="text-xs font-black uppercase tracking-wider text-muted-foreground">{metric.label}</p>
            <div className="mt-3 flex items-end justify-between gap-3">
              <p className="text-3xl font-black">{metric.value}</p>
              <span className={`h-3 w-3 rounded-full ${metric.tone === "danger" ? "bg-red-500" : metric.tone === "warning" ? "bg-amber-500" : metric.tone === "positive" ? "bg-emerald-500" : "bg-primary"}`} />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function ModuleTab({ value, icon: Icon, label }: { value: string; icon: typeof Landmark; label: string }) {
  return <TabsTrigger value={value} className="h-11 rounded-xl px-4"><Icon className="h-4 w-4" />{label}</TabsTrigger>;
}

function LoadingPanel() {
  return <div className="flex min-h-48 items-center justify-center rounded-2xl border bg-card"><Loader2 className="h-6 w-6 animate-spin text-primary" /></div>;
}

function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return <label className="block space-y-2"><span className="text-xs font-black uppercase tracking-wide text-muted-foreground">{label}</span>{children}{hint ? <span className="block text-xs text-muted-foreground">{hint}</span> : null}</label>;
}

function StatusBadge({ value }: { value: string }) {
  const destructive = ["failed", "rejected", "critical", "defaulted", "written_off", "posting_failed"].includes(value);
  return <Badge variant={destructive ? "destructive" : value.includes("complete") || value === "matched" || value === "active" || value === "submitted" ? "default" : "secondary"}>{titleCase(value)}</Badge>;
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return <div className="rounded-2xl border border-dashed p-8 text-center"><p className="font-black">{title}</p><p className="mt-1 text-sm text-muted-foreground">{description}</p></div>;
}

function CDASWorkspace({
  clients, loans, clientOptions, loanOptions, profiles, mandates, batches, affordability, setAffordability, working, runAction,
}: {
  clients: CompanyClient[];
  loans: Loan[];
  clientOptions: Array<{ value: string; label: string; description: string; keywords: string[] }>;
  loanOptions: Array<{ value: string; label: string; description: string; keywords: string[] }>;
  profiles: CDASPayrollProfile[];
  mandates: CDASMandate[];
  batches: CDASRemittanceBatch[];
  affordability: CDASAffordability | null;
  setAffordability: (value: CDASAffordability | null) => void;
  working: boolean;
  runAction: (action: () => Promise<unknown>) => Promise<void>;
}) {
  const [borrowerId, setBorrowerId] = useState("");
  const [employeeNumber, setEmployeeNumber] = useState("");
  const [department, setDepartment] = useState("");
  const [grossSalary, setGrossSalary] = useState("");
  const [netSalary, setNetSalary] = useState("");
  const [existingDeductions, setExistingDeductions] = useState("0");
  const [maxPercent, setMaxPercent] = useState("40");
  const [verified, setVerified] = useState(false);
  const [loanId, setLoanId] = useState("");
  const [monthlyDeduction, setMonthlyDeduction] = useState("");
  const [installments, setInstallments] = useState("1");
  const [startDate, setStartDate] = useState(today);
  const [batchMonth, setBatchMonth] = useState(`${today.slice(0, 7)}-01`);
  const [batchReference, setBatchReference] = useState("");
  const selectedProfile = profiles.find((item) => item.borrower_id === borrowerId);
  const borrowerLoans = loans.filter((item) => item.borrower_id === borrowerId);
  const borrowerLoanOptions = loanOptions.filter((option) => borrowerLoans.some((loan) => loan.id === option.value));
  const selectedClient = clients.find((item) => item.borrower_id === borrowerId);

  async function saveProfile() {
    if (!borrowerId || !employeeNumber || !netSalary) throw new Error("Select a borrower and enter payroll details.");
    await lendingOperationsApi.savePayrollProfile({
      borrower_id: borrowerId,
      employee_number: employeeNumber,
      ministry_department: department || null,
      gross_salary: Number(grossSalary || 0),
      net_salary: Number(netSalary),
      existing_deductions: Number(existingDeductions || 0),
      maximum_deduction_percent: Number(maxPercent || 40),
      verified,
      verification_reference: verified ? `MANUAL-${Date.now()}` : null,
    });
    toast.success("CDAS payroll profile saved.");
  }

  async function calculate() {
    if (!monthlyDeduction) throw new Error("Enter a proposed monthly deduction.");
    const result = await lendingOperationsApi.calculateCDASAffordability({
      payroll_profile_id: selectedProfile?.id,
      net_salary: selectedProfile ? undefined : Number(netSalary || 0),
      existing_deductions: selectedProfile ? undefined : Number(existingDeductions || 0),
      proposed_deduction: Number(monthlyDeduction),
      maximum_deduction_percent: selectedProfile ? undefined : Number(maxPercent || 40),
    });
    setAffordability(result);
  }

  async function createMandate() {
    if (!borrowerId || !loanId || !selectedProfile) throw new Error("Select a borrower, payroll profile and loan.");
    await lendingOperationsApi.createCDASMandate({
      borrower_id: borrowerId,
      loan_id: loanId,
      payroll_profile_id: selectedProfile.id,
      monthly_deduction: Number(monthlyDeduction),
      start_date: startDate,
      expected_installments: Number(installments),
      borrower_consent: true,
    });
    toast.success("CDAS deduction mandate created.");
  }

  return (
    <>
      <div className="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
        <Card className="rounded-3xl">
          <CardHeader><CardTitle>Employee payroll profile</CardTitle><CardDescription>Capture the verified government employee information used for CDAS affordability and deduction mandates.</CardDescription></CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2"><Field label="Borrower"><SearchableCombobox value={borrowerId} onValueChange={(value) => { setBorrowerId(value); const profile = profiles.find((item) => item.borrower_id === value); if (profile) { setEmployeeNumber(profile.employee_number); setDepartment(profile.ministry_department ?? ""); setGrossSalary(String(profile.gross_salary)); setNetSalary(String(profile.net_salary)); setExistingDeductions(String(profile.existing_deductions)); setMaxPercent(String(profile.maximum_deduction_percent)); setVerified(profile.verified); } }} options={clientOptions} placeholder="Search borrower by name, phone or ID" /></Field></div>
            <Field label="Employee number"><Input className="h-11" value={employeeNumber} onChange={(event) => setEmployeeNumber(event.target.value)} /></Field>
            <Field label="Ministry / department"><Input className="h-11" value={department} onChange={(event) => setDepartment(event.target.value)} /></Field>
            <Field label="Gross salary"><Input className="h-11" type="number" min="0" value={grossSalary} onChange={(event) => setGrossSalary(event.target.value)} /></Field>
            <Field label="Verified net salary"><Input className="h-11" type="number" min="0" value={netSalary} onChange={(event) => setNetSalary(event.target.value)} /></Field>
            <Field label="Existing payroll deductions"><Input className="h-11" type="number" min="0" value={existingDeductions} onChange={(event) => setExistingDeductions(event.target.value)} /></Field>
            <Field label="Maximum deduction %"><Input className="h-11" type="number" min="0" max="100" value={maxPercent} onChange={(event) => setMaxPercent(event.target.value)} /></Field>
            <label className="flex items-center gap-3 rounded-xl border p-3 sm:col-span-2"><input type="checkbox" checked={verified} onChange={(event) => setVerified(event.target.checked)} /><span><span className="block text-sm font-black">Payroll information verified</span><span className="text-xs text-muted-foreground">Use only after checking authorised payroll evidence.</span></span></label>
            <Button disabled={working} onClick={() => void runAction(saveProfile)} className="h-11 sm:col-span-2"><BadgeCheck className="h-4 w-4" />Save payroll profile</Button>
          </CardContent>
        </Card>

        <Card className="rounded-3xl">
          <CardHeader><CardTitle>Affordability and mandate</CardTitle><CardDescription>Test available salary-deduction capacity before creating a borrower-authorised mandate.</CardDescription></CardHeader>
          <CardContent className="space-y-4">
            <Field label="Loan"><SearchableCombobox value={loanId} onValueChange={setLoanId} options={borrowerLoanOptions} placeholder={borrowerId ? "Select borrower loan" : "Select borrower first"} disabled={!borrowerId} /></Field>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Monthly deduction"><Input className="h-11" type="number" min="0" value={monthlyDeduction} onChange={(event) => setMonthlyDeduction(event.target.value)} /></Field>
              <Field label="Start date"><Input className="h-11" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></Field>
              <Field label="Deductions"><Input className="h-11" type="number" min="1" value={installments} onChange={(event) => setInstallments(event.target.value)} /></Field>
            </div>
            <Button variant="outline" className="w-full" disabled={working} onClick={() => void runAction(calculate)}><Scale className="h-4 w-4" />Calculate affordability</Button>
            {affordability ? (
              <div className={`rounded-2xl border p-4 ${affordability.affordable ? "border-emerald-300 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950/30" : "border-red-300 bg-red-50 dark:border-red-900 dark:bg-red-950/30"}`}>
                <div className="flex items-center justify-between"><p className="font-black">{affordability.affordable ? "Affordable" : "Not affordable"}</p><StatusBadge value={affordability.affordable ? "matched" : "rejected"} /></div>
                <div className="mt-3 grid grid-cols-2 gap-3 text-sm"><Metric label="Available capacity" value={formatMoney(affordability.available_deduction_capacity)} /><Metric label="Take-home after" value={formatMoney(affordability.take_home_after)} /><Metric label="Deduction ratio" value={`${affordability.deduction_ratio_percent}%`} /><Metric label="Maximum deductions" value={formatMoney(affordability.maximum_total_deductions)} /></div>
                {affordability.reasons.length ? <ul className="mt-3 space-y-1 text-xs">{affordability.reasons.map((reason) => <li key={reason}>• {reason}</li>)}</ul> : null}
              </div>
            ) : null}
            <Button className="w-full" disabled={working || !affordability?.affordable || !selectedProfile} onClick={() => void runAction(createMandate)}><Plus className="h-4 w-4" />Create borrower-authorised mandate</Button>
            {selectedClient ? <p className="text-xs text-muted-foreground">Selected employee: {selectedClient.full_name} · {selectedClient.phone}</p> : null}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card className="rounded-3xl">
          <CardHeader><CardTitle>CDAS deduction mandates</CardTitle><CardDescription>Track submission, acceptance, active deductions, rescheduling and completion.</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {mandates.length ? mandates.map((mandate) => (
              <div key={mandate.id} className="rounded-2xl border p-4">
                <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-mono text-xs font-black text-primary">{mandate.mandate_number}</p><p className="mt-1 font-black">Employee {mandate.employee_number}</p></div><StatusBadge value={mandate.status} /></div>
                <div className="mt-3 grid grid-cols-2 gap-3 text-sm"><Metric label="Monthly deduction" value={formatMoney(mandate.monthly_deduction)} /><Metric label="Received" value={`${mandate.deductions_received}/${mandate.expected_installments}`} /><Metric label="Expected total" value={formatMoney(mandate.total_expected)} /><Metric label="Received total" value={formatMoney(mandate.total_received)} /></div>
                {mandate.status === "draft" ? <Button className="mt-3 w-full" size="sm" variant="outline" disabled={working} onClick={() => void runAction(async () => { await lendingOperationsApi.updateCDASMandateStatus(mandate.id, { status: "submitted" }); toast.success("Mandate marked as submitted."); })}>Submit mandate</Button> : null}
              </div>
            )) : <EmptyState title="No CDAS mandates" description="Create a verified payroll profile and an affordable deduction mandate." />}
          </CardContent>
        </Card>

        <Card className="rounded-3xl">
          <CardHeader><CardTitle>Monthly remittance batches</CardTitle><CardDescription>Import or manually capture the consolidated CDAS payroll remittance, then reconcile it to mandates and loan balances.</CardDescription></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2"><Field label="Payroll month"><Input className="h-11" type="date" value={batchMonth} onChange={(event) => setBatchMonth(event.target.value)} /></Field><Field label="Batch reference"><Input className="h-11" value={batchReference} onChange={(event) => setBatchReference(event.target.value)} placeholder="CDAS-2026-07" /></Field></div>
            <Button className="w-full" variant="outline" disabled={working} onClick={() => void runAction(async () => { if (!batchReference) throw new Error("Enter a batch reference."); await lendingOperationsApi.createCDASBatch({ payroll_month: batchMonth, batch_reference: batchReference, source: "manual" }); setBatchReference(""); toast.success("CDAS remittance batch created."); })}><Plus className="h-4 w-4" />Create remittance batch</Button>
            <div className="space-y-3">
              {batches.map((batch) => <CDASBatchCard key={batch.id} batch={batch} mandates={mandates} working={working} runAction={runAction} />)}
              {!batches.length ? <EmptyState title="No remittance batches" description="Create the first payroll-month remittance batch." /> : null}
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function CDASBatchCard({ batch, mandates, working, runAction }: { batch: CDASRemittanceBatch; mandates: CDASMandate[]; working: boolean; runAction: (action: () => Promise<unknown>) => Promise<void> }) {
  const [employeeNumber, setEmployeeNumber] = useState("");
  const [lineReference, setLineReference] = useState("");
  const [amount, setAmount] = useState("");
  const activeMandate = mandates.find((item) => item.employee_number === employeeNumber && ["accepted", "active", "rescheduled"].includes(item.status));
  return <div className="rounded-2xl border p-4">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-mono text-xs font-black text-primary">{batch.batch_reference}</p><p className="mt-1 text-sm text-muted-foreground">Payroll month {formatDate(batch.payroll_month)}</p></div><StatusBadge value={batch.status} /></div>
    <div className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4"><Metric label="Received" value={formatMoney(batch.received_amount)} /><Metric label="Matched" value={formatMoney(batch.matched_amount)} /><Metric label="Exceptions" value={String(batch.exception_count)} /><Metric label="Lines" value={String(batch.line_count)} /></div>
    {!batch.status.startsWith("reconciled") ? <div className="mt-4 grid gap-2 sm:grid-cols-[1fr_1fr_0.7fr_auto]"><Input className="h-10" value={employeeNumber} onChange={(event) => setEmployeeNumber(event.target.value)} placeholder="Employee number" /><Input className="h-10" value={lineReference} onChange={(event) => setLineReference(event.target.value)} placeholder="Line reference" /><Input className="h-10" type="number" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="Amount" /><Button size="sm" disabled={working} onClick={() => void runAction(async () => { if (!employeeNumber || !lineReference || !amount) throw new Error("Complete the remittance line."); await lendingOperationsApi.createCDASBatchLine(batch.id, { employee_number: employeeNumber, line_reference: lineReference, deducted_amount: Number(amount), expected_amount: activeMandate?.monthly_deduction }); setEmployeeNumber(""); setLineReference(""); setAmount(""); toast.success("Remittance line added."); })}><Plus className="h-4 w-4" />Line</Button></div> : null}
    {!batch.status.startsWith("reconciled") && batch.line_count > 0 ? <Button className="mt-3 w-full" disabled={working} onClick={() => void runAction(async () => { await lendingOperationsApi.reconcileCDASBatch(batch.id); toast.success("CDAS batch reconciled and matched deductions were posted to loans."); })}><Scale className="h-4 w-4" />Reconcile and post deductions</Button> : null}
  </div>;
}

function ReconciliationWorkspace({ runs, exceptions, working, runAction }: { runs: ReconciliationRun[]; exceptions: ReconciliationException[]; working: boolean; runAction: (action: () => Promise<unknown>) => Promise<void> }) {
  const [runType, setRunType] = useState("full");
  const [from, setFrom] = useState(yearStart);
  const [to, setTo] = useState(today);
  return <>
    <div className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">
      <Card className="rounded-3xl"><CardHeader><CardTitle>Run automated reconciliation</CardTitle><CardDescription>Compare loans, payments, allocations, receipts, accounting journals and CDAS deductions.</CardDescription></CardHeader><CardContent className="space-y-4"><Field label="Reconciliation scope"><NativeSelect className="h-11" value={runType} onChange={(event) => setRunType(event.target.value)}><option value="full">Full financial reconciliation</option><option value="payments">Payments, receipts and allocations</option><option value="loans">Loan balances</option><option value="accounting">Accounting linkage</option><option value="cdas">CDAS deductions</option></NativeSelect></Field><div className="grid gap-3 sm:grid-cols-2"><Field label="From"><Input className="h-11" type="date" value={from} onChange={(event) => setFrom(event.target.value)} /></Field><Field label="To"><Input className="h-11" type="date" value={to} onChange={(event) => setTo(event.target.value)} /></Field></div><Button className="w-full" disabled={working} onClick={() => void runAction(async () => { await lendingOperationsApi.runReconciliation({ run_type: runType, period_start: from, period_end: to }); toast.success("Reconciliation completed."); })}><Scale className="h-4 w-4" />Run reconciliation</Button></CardContent></Card>
      <Card className="rounded-3xl"><CardHeader><CardTitle>Recent reconciliation runs</CardTitle><CardDescription>Each run preserves totals, exceptions and the selected period.</CardDescription></CardHeader><CardContent className="grid gap-3 sm:grid-cols-2">{runs.map((run) => <div key={run.id} className="rounded-2xl border p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-mono text-xs font-black text-primary">{run.run_reference}</p><p className="mt-1 font-black">{titleCase(run.run_type)}</p></div><StatusBadge value={run.status} /></div><div className="mt-3 grid grid-cols-2 gap-3 text-sm"><Metric label="Checked" value={String(run.records_checked)} /><Metric label="Matched" value={String(run.matched_records)} /><Metric label="Exceptions" value={String(run.exception_records)} /><Metric label="Variance" value={formatMoney(run.exception_amount)} /></div></div>)}{!runs.length ? <EmptyState title="No reconciliation runs" description="Run the first controlled reconciliation." /> : null}</CardContent></Card>
    </div>
    <Card className="rounded-3xl"><CardHeader><CardTitle>Exception work queue</CardTitle><CardDescription>Investigate and resolve discrepancies without editing historic financial records.</CardDescription></CardHeader><CardContent className="grid gap-3 lg:grid-cols-2">{exceptions.map((item) => <div key={item.id} className="rounded-2xl border p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-black uppercase tracking-wide text-muted-foreground">{titleCase(item.exception_type)}</p><p className="mt-1 font-black">{item.reference ?? "No external reference"}</p></div><div className="flex gap-2"><StatusBadge value={item.severity} /><StatusBadge value={item.status} /></div></div><p className="mt-3 text-sm leading-6 text-muted-foreground">{item.description}</p><div className="mt-3 grid grid-cols-3 gap-2 text-sm"><Metric label="Expected" value={formatMoney(item.expected_amount)} /><Metric label="Actual" value={formatMoney(item.actual_amount)} /><Metric label="Variance" value={formatMoney(item.variance_amount)} /></div>{!(["resolved", "accepted_variance", "dismissed"].includes(item.status)) ? <Button className="mt-3 w-full" size="sm" variant="outline" disabled={working} onClick={() => void runAction(async () => { await lendingOperationsApi.updateReconciliationException(item.id, { status: "resolved", resolution_notes: "Reviewed and resolved from the LoanHub reconciliation work queue." }); toast.success("Exception resolved."); })}><CheckCircle2 className="h-4 w-4" />Mark resolved</Button> : null}</div>)}{!exceptions.length ? <EmptyState title="No exceptions" description="No reconciliation exceptions are currently recorded." /> : null}</CardContent></Card>
  </>;
}

function CreditBureauWorkspace({ clients, clientOptions, enquiries, working, runAction }: { clients: CompanyClient[]; clientOptions: Array<{ value: string; label: string; description: string; keywords: string[] }>; enquiries: CreditBureauEnquiry[]; working: boolean; runAction: (action: () => Promise<unknown>) => Promise<void> }) {
  const [borrowerId, setBorrowerId] = useState("");
  const [provider, setProvider] = useState("manual");
  const [selectedId, setSelectedId] = useState("");
  const [score, setScore] = useState("");
  const [exposure, setExposure] = useState("0");
  const [obligations, setObligations] = useState("0");
  const selectedClient = clients.find((client) => client.borrower_id === borrowerId);
  return <div className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
    <div className="space-y-5">
      <Card className="rounded-3xl"><CardHeader><CardTitle>Request credit enquiry</CardTitle><CardDescription>Credit consent is mandatory. External provider calls remain disabled until official credentials and API specifications are configured.</CardDescription></CardHeader><CardContent className="space-y-4"><Field label="Borrower"><SearchableCombobox value={borrowerId} onValueChange={setBorrowerId} options={clientOptions} placeholder="Search borrower" /></Field><Field label="Provider"><NativeSelect className="h-11" value={provider} onChange={(event) => setProvider(event.target.value)}><option value="manual">Manual / uploaded report</option><option value="experian">Experian (configuration required)</option><option value="sandbox">LoanHub sandbox</option></NativeSelect></Field>{selectedClient && !selectedClient.consent_to_credit_checks ? <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200"><AlertTriangle className="mr-2 inline h-4 w-4" />This borrower has not recorded consent to credit checks.</div> : null}<Button className="w-full" disabled={working || !borrowerId || !selectedClient?.consent_to_credit_checks} onClick={() => void runAction(async () => { await lendingOperationsApi.createCreditEnquiry({ borrower_id: borrowerId, provider, consent_confirmed: true, purpose: "credit_assessment" }); toast.success("Credit enquiry created."); })}><SearchCheck className="h-4 w-4" />Create enquiry</Button></CardContent></Card>
      <Card className="rounded-3xl"><CardHeader><CardTitle>Capture bureau response</CardTitle><CardDescription>Use this for an authorised manual report or a response returned by a configured provider connector.</CardDescription></CardHeader><CardContent className="space-y-4"><Field label="Pending enquiry"><SearchableCombobox value={selectedId} onValueChange={setSelectedId} options={enquiries.filter((item) => item.status !== "completed").map((item) => ({ value: item.id, label: item.enquiry_reference, description: titleCase(item.provider) }))} placeholder="Select enquiry" /></Field><div className="grid gap-3 sm:grid-cols-3"><Field label="Credit score"><Input className="h-11" type="number" value={score} onChange={(event) => setScore(event.target.value)} /></Field><Field label="Current exposure"><Input className="h-11" type="number" value={exposure} onChange={(event) => setExposure(event.target.value)} /></Field><Field label="Monthly obligations"><Input className="h-11" type="number" value={obligations} onChange={(event) => setObligations(event.target.value)} /></Field></div><Button className="w-full" disabled={working || !selectedId} onClick={() => void runAction(async () => { await lendingOperationsApi.completeCreditEnquiry(selectedId, { status: "completed", score: Number(score || 0), current_exposure: Number(exposure || 0), monthly_obligations: Number(obligations || 0), risk_grade: Number(score || 0) >= 700 ? "low" : Number(score || 0) >= 550 ? "medium" : "high", response_data: { captured_manually: true } }); toast.success("Credit report response recorded."); })}><ClipboardCheck className="h-4 w-4" />Complete enquiry</Button></CardContent></Card>
    </div>
    <Card className="rounded-3xl"><CardHeader><CardTitle>Credit enquiry register</CardTitle><CardDescription>Full history of consented enquiries, scores, exposure and adverse records.</CardDescription></CardHeader><CardContent className="grid gap-3 md:grid-cols-2">{enquiries.map((item) => <div key={item.id} className="rounded-2xl border p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-mono text-xs font-black text-primary">{item.enquiry_reference}</p><p className="mt-1 font-black">{titleCase(item.provider)}</p></div><StatusBadge value={item.status} /></div><div className="mt-3 grid grid-cols-2 gap-3 text-sm"><Metric label="Score" value={item.score == null ? "Pending" : String(item.score)} /><Metric label="Risk grade" value={item.risk_grade ? titleCase(item.risk_grade) : "Pending"} /><Metric label="Exposure" value={formatMoney(item.current_exposure)} /><Metric label="Monthly obligations" value={formatMoney(item.monthly_obligations)} /></div><p className="mt-3 text-xs text-muted-foreground">Requested {formatDateTime(item.requested_at)}</p></div>)}{!enquiries.length ? <EmptyState title="No bureau enquiries" description="Create a consented credit enquiry for a company borrower." /> : null}</CardContent></Card>
  </div>;
}

function ComplianceWorkspace({ clientOptions, cases, working, runAction }: { clientOptions: Array<{ value: string; label: string; description: string; keywords: string[] }>; cases: ComplianceCase[]; working: boolean; runAction: (action: () => Promise<unknown>) => Promise<void> }) {
  const [borrowerId, setBorrowerId] = useState("");
  const [caseType, setCaseType] = useState("kyc");
  const [severity, setSeverity] = useState("medium");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [screenType, setScreenType] = useState("identity");
  return <div className="grid gap-5 xl:grid-cols-[0.75fr_1.25fr]">
    <Card className="rounded-3xl"><CardHeader><CardTitle>Open compliance case</CardTitle><CardDescription>Centralise KYC, AML, sanctions, PEP, adverse media and fraud investigations.</CardDescription></CardHeader><CardContent className="space-y-4"><Field label="Borrower"><SearchableCombobox value={borrowerId} onValueChange={setBorrowerId} options={clientOptions} placeholder="Search borrower" allowClear /></Field><div className="grid gap-3 sm:grid-cols-2"><Field label="Case type"><NativeSelect className="h-11" value={caseType} onChange={(event) => setCaseType(event.target.value)}><option value="kyc">KYC verification</option><option value="aml">AML investigation</option><option value="fraud">Fraud review</option><option value="sanctions">Sanctions</option><option value="pep">Politically exposed person</option><option value="adverse_media">Adverse media</option><option value="source_of_funds">Source of funds</option></NativeSelect></Field><Field label="Severity"><NativeSelect className="h-11" value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></NativeSelect></Field></div><Field label="Case title"><Input className="h-11" value={title} onChange={(event) => setTitle(event.target.value)} /></Field><Field label="Description"><Textarea value={description} onChange={(event) => setDescription(event.target.value)} /></Field><Button className="w-full" disabled={working || !title} onClick={() => void runAction(async () => { await lendingOperationsApi.createComplianceCase({ borrower_id: borrowerId || null, case_type: caseType, severity, title, description: description || null }); setTitle(""); setDescription(""); toast.success("Compliance case opened."); })}><Plus className="h-4 w-4" />Open case</Button></CardContent></Card>
    <Card className="rounded-3xl"><CardHeader><CardTitle>Compliance investigation queue</CardTitle><CardDescription>Run screenings, escalate matches and close cleared investigations with an audit trail.</CardDescription></CardHeader><CardContent className="space-y-3">{cases.map((item) => <div key={item.id} className="rounded-2xl border p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-mono text-xs font-black text-primary">{item.case_reference}</p><p className="mt-1 font-black">{item.title}</p></div><div className="flex gap-2"><StatusBadge value={item.severity} /><StatusBadge value={item.status} /></div></div><p className="mt-2 text-sm leading-6 text-muted-foreground">{item.description || "No description."}</p>{item.flags.length ? <div className="mt-3 flex flex-wrap gap-2">{item.flags.map((flag) => <Badge key={flag} variant="destructive">{titleCase(flag)}</Badge>)}</div> : null}<div className="mt-4 grid gap-2 sm:grid-cols-[1fr_auto_auto]"><NativeSelect className="h-10" value={screenType} onChange={(event) => setScreenType(event.target.value)}><option value="identity">Identity</option><option value="sanctions">Sanctions</option><option value="pep">PEP</option><option value="adverse_media">Adverse media</option><option value="fraud">Fraud</option><option value="device">Device risk</option><option value="document">Document authenticity</option><option value="source_of_funds">Source of funds</option></NativeSelect><Button size="sm" variant="outline" disabled={working} onClick={() => void runAction(async () => { await lendingOperationsApi.createComplianceScreening(item.id, { screening_type: screenType, provider: "manual", matched: false, match_score: 0, result: { reviewed: true } }); toast.success("Screening recorded as clear."); })}><ShieldCheck className="h-4 w-4" />Clear screening</Button><Button size="sm" variant="outline" disabled={working} onClick={() => void runAction(async () => { await lendingOperationsApi.createComplianceScreening(item.id, { screening_type: screenType, provider: "manual", matched: true, match_score: 100, result: { manual_match: true }, notes: "Manual match requires enhanced review." }); toast.warning("Screening match escalated."); })}><ShieldAlert className="h-4 w-4" />Record match</Button></div>{!(["cleared", "closed"].includes(item.status)) ? <Button className="mt-3 w-full" size="sm" disabled={working} onClick={() => void runAction(async () => { await lendingOperationsApi.updateComplianceCase(item.id, { status: "cleared", resolution: "All required checks completed and cleared." }); toast.success("Compliance case cleared."); })}><CheckCircle2 className="h-4 w-4" />Clear and close case</Button> : null}</div>)}{!cases.length ? <EmptyState title="No compliance cases" description="Create a KYC, AML or fraud case when enhanced review is required." /> : null}</CardContent></Card>
  </div>;
}

function CollectionsWorkspace({ loans, loanOptions, cases, working, runAction }: { loans: Loan[]; loanOptions: Array<{ value: string; label: string; description: string; keywords: string[] }>; cases: CollectionCase[]; working: boolean; runAction: (action: () => Promise<unknown>) => Promise<void> }) {
  const [loanId, setLoanId] = useState("");
  const [activityType, setActivityType] = useState("call");
  const [activityNotes, setActivityNotes] = useState("");
  const [followUp, setFollowUp] = useState("");
  const eligibleLoans = loanOptions.filter((option) => { const loan = loans.find((item) => item.id === option.value); return loan && loan.balance > 0; });
  return <>
    <div className="grid gap-5 lg:grid-cols-[0.75fr_1.25fr]">
      <Card className="rounded-3xl"><CardHeader><CardTitle>Recoveries control</CardTitle><CardDescription>Synchronise overdue instalments into collection cases or open a controlled case manually.</CardDescription></CardHeader><CardContent className="space-y-4"><Button className="w-full" disabled={working} onClick={() => void runAction(async () => { const result = await lendingOperationsApi.syncOverdueCases(); toast.success(result.message); })}><RefreshCcw className="h-4 w-4" />Sync overdue loans</Button><Field label="Open case manually"><SearchableCombobox value={loanId} onValueChange={setLoanId} options={eligibleLoans} placeholder="Search loan number" /></Field><Button variant="outline" className="w-full" disabled={working || !loanId} onClick={() => void runAction(async () => { await lendingOperationsApi.createCollectionCase({ loan_id: loanId, priority: "normal" }); toast.success("Collection case opened."); })}><Plus className="h-4 w-4" />Open collection case</Button></CardContent></Card>
      <Card className="rounded-3xl"><CardHeader><CardTitle>Portfolio arrears summary</CardTitle><CardDescription>Cases are prioritised by days past due, overdue amount and recovery stage.</CardDescription></CardHeader><CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><MetricCard title="Open cases" value={String(cases.filter((item) => !["closed", "recovered"].includes(item.status)).length)} icon={HandCoins} /><MetricCard title="Overdue exposure" value={formatMoney(cases.reduce((sum, item) => sum + Number(item.overdue_amount), 0))} icon={AlertTriangle} /><MetricCard title="Urgent cases" value={String(cases.filter((item) => item.priority === "urgent").length)} icon={ShieldAlert} /><MetricCard title="Recovered" value={formatMoney(cases.reduce((sum, item) => sum + Number(item.recovered_amount), 0))} icon={CheckCircle2} /></CardContent></Card>
    </div>
    <Card className="rounded-3xl"><CardHeader><CardTitle>Collection case work queue</CardTitle><CardDescription>Capture calls, messages, visits, promises to pay, restructures and legal handovers.</CardDescription></CardHeader><CardContent className="grid gap-4 xl:grid-cols-2">{cases.map((item) => <div key={item.id} className="rounded-2xl border p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-mono text-xs font-black text-primary">{item.case_reference}</p><p className="mt-1 font-black">{item.days_past_due} days past due</p></div><div className="flex gap-2"><StatusBadge value={item.priority} /><StatusBadge value={item.status} /></div></div><div className="mt-3 grid grid-cols-2 gap-3 text-sm"><Metric label="Overdue" value={formatMoney(item.overdue_amount)} /><Metric label="Loan balance" value={formatMoney(item.outstanding_balance)} /><Metric label="Stage" value={titleCase(item.stage)} /><Metric label="Recovered" value={formatMoney(item.recovered_amount)} /></div><div className="mt-4 grid gap-2 sm:grid-cols-2"><NativeSelect className="h-10" value={activityType} onChange={(event) => setActivityType(event.target.value)}><option value="call">Phone call</option><option value="sms">SMS</option><option value="email">Email</option><option value="visit">Field visit</option><option value="letter">Demand letter</option><option value="promise">Promise to pay</option><option value="restructure">Restructure discussion</option><option value="legal_handover">Legal handover</option><option value="note">Internal note</option></NativeSelect><Input className="h-10" type="datetime-local" value={followUp} onChange={(event) => setFollowUp(event.target.value)} /></div><Textarea className="mt-2" value={activityNotes} onChange={(event) => setActivityNotes(event.target.value)} placeholder="Outcome, promise or follow-up details" /><Button className="mt-3 w-full" size="sm" variant="outline" disabled={working} onClick={() => void runAction(async () => { await lendingOperationsApi.createCollectionActivity(item.id, { activity_type: activityType, notes: activityNotes || null, outcome: "recorded", follow_up_at: followUp ? new Date(followUp).toISOString() : null }); setActivityNotes(""); setFollowUp(""); toast.success("Collection activity recorded."); })}><Plus className="h-4 w-4" />Record activity</Button></div>)}{!cases.length ? <EmptyState title="No collection cases" description="Synchronise overdue loans to create the recoveries work queue." /> : null}</CardContent></Card>
  </>;
}

function RegulatoryWorkspace({ submissions, working, runAction }: { submissions: RegulatorySubmission[]; working: boolean; runAction: (action: () => Promise<unknown>) => Promise<void> }) {
  const [reportType, setReportType] = useState("full_return");
  const [from, setFrom] = useState(yearStart);
  const [to, setTo] = useState(today);
  return <div className="grid gap-5 xl:grid-cols-[0.7fr_1.3fr]">
    <Card className="rounded-3xl"><CardHeader><CardTitle>Prepare regulatory return</CardTitle><CardDescription>Create a versioned return from the live portfolio, payment, arrears and compliance records.</CardDescription></CardHeader><CardContent className="space-y-4"><Field label="Return type"><NativeSelect className="h-11" value={reportType} onChange={(event) => setReportType(event.target.value)}><option value="full_return">Full regulatory return</option><option value="portfolio">Loan portfolio</option><option value="arrears">Arrears and collections</option><option value="provisions">Provisions</option><option value="write_offs">Write-offs and recoveries</option><option value="aml">AML / compliance</option><option value="liquidity">Liquidity</option><option value="consumer_protection">Consumer protection</option><option value="credit_reporting">Credit reporting</option></NativeSelect></Field><div className="grid gap-3 sm:grid-cols-2"><Field label="Period start"><Input className="h-11" type="date" value={from} onChange={(event) => setFrom(event.target.value)} /></Field><Field label="Period end"><Input className="h-11" type="date" value={to} onChange={(event) => setTo(event.target.value)} /></Field></div><Button className="w-full" disabled={working} onClick={() => void runAction(async () => { await lendingOperationsApi.createRegulatorySubmission({ report_type: reportType, period_start: from, period_end: to }); toast.success("Regulatory return created in draft."); })}><Plus className="h-4 w-4" />Create draft return</Button></CardContent></Card>
    <Card className="rounded-3xl"><CardHeader><CardTitle>Regulatory submission register</CardTitle><CardDescription>Generate, validate, approve and record the regulator submission reference.</CardDescription></CardHeader><CardContent className="grid gap-3 md:grid-cols-2">{submissions.map((item) => <div key={item.id} className="rounded-2xl border p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-mono text-xs font-black text-primary">{item.submission_reference}</p><p className="mt-1 font-black">{titleCase(item.report_type)}</p></div><StatusBadge value={item.status} /></div><p className="mt-2 text-sm text-muted-foreground">{formatDate(item.period_start)} – {formatDate(item.period_end)}</p><div className="mt-3 flex flex-wrap gap-2">{item.status === "draft" ? <Button size="sm" variant="outline" disabled={working} onClick={() => void runAction(async () => { await lendingOperationsApi.generateRegulatorySubmission(item.id); toast.success("Regulatory payload generated."); })}><FileChartColumn className="h-4 w-4" />Generate</Button> : null}{item.status === "generated" ? <Button size="sm" variant="outline" disabled={working} onClick={() => void runAction(async () => { await lendingOperationsApi.updateRegulatorySubmission(item.id, { status: "approved" }); toast.success("Regulatory return approved."); })}><BookOpenCheck className="h-4 w-4" />Approve</Button> : null}{item.status === "approved" ? <Button size="sm" disabled={working} onClick={() => void runAction(async () => { await lendingOperationsApi.updateRegulatorySubmission(item.id, { status: "submitted", regulator_reference: `REGULATOR-${Date.now()}` }); toast.success("Submission recorded."); })}><CheckCircle2 className="h-4 w-4" />Mark submitted</Button> : null}</div>{Object.keys(item.payload || {}).length ? <details className="mt-3 rounded-xl bg-muted/50 p-3"><summary className="cursor-pointer text-xs font-black">View generated data</summary><pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap text-[11px]">{JSON.stringify(item.payload, null, 2)}</pre></details> : null}</div>)}{!submissions.length ? <EmptyState title="No regulatory returns" description="Create the first controlled reporting period." /> : null}</CardContent></Card>
  </div>;
}

function DecisionWorkspace({ clientOptions, loanOptions, policies, decisions, templates, instances, working, runAction }: { clientOptions: Array<{ value: string; label: string; description: string; keywords: string[] }>; loanOptions: Array<{ value: string; label: string; description: string; keywords: string[] }>; policies: CreditDecisionPolicy[]; decisions: CreditDecision[]; templates: WorkflowTemplate[]; instances: WorkflowInstance[]; working: boolean; runAction: (action: () => Promise<unknown>) => Promise<void> }) {
  const [policyName, setPolicyName] = useState("Standard lending policy");
  const [minimumScore, setMinimumScore] = useState("550");
  const [maximumDti, setMaximumDti] = useState("40");
  const [minimumIncome, setMinimumIncome] = useState("0");
  const [maximumAmount, setMaximumAmount] = useState("100000");
  const [borrowerId, setBorrowerId] = useState("");
  const [policyId, setPolicyId] = useState("");
  const [requestedAmount, setRequestedAmount] = useState("");
  const [proposedInstallment, setProposedInstallment] = useState("");
  const [workflowName, setWorkflowName] = useState("Standard loan approval");
  const [templateId, setTemplateId] = useState("");
  const [loanId, setLoanId] = useState("");
  const activePolicies = policies.filter((item) => item.status === "active");
  const activeTemplates = templates.filter((item) => item.status === "active");
  return <>
    <div className="grid gap-5 xl:grid-cols-2">
      <Card className="rounded-3xl"><CardHeader><CardTitle>Credit decision policy</CardTitle><CardDescription>Version the automatic approval, referral and decline rules used by the company.</CardDescription></CardHeader><CardContent className="space-y-4"><Field label="Policy name"><Input className="h-11" value={policyName} onChange={(event) => setPolicyName(event.target.value)} /></Field><div className="grid gap-3 sm:grid-cols-2"><Field label="Minimum credit score"><Input className="h-11" type="number" value={minimumScore} onChange={(event) => setMinimumScore(event.target.value)} /></Field><Field label="Maximum DTI %"><Input className="h-11" type="number" value={maximumDti} onChange={(event) => setMaximumDti(event.target.value)} /></Field><Field label="Minimum net income"><Input className="h-11" type="number" value={minimumIncome} onChange={(event) => setMinimumIncome(event.target.value)} /></Field><Field label="Automatic amount limit"><Input className="h-11" type="number" value={maximumAmount} onChange={(event) => setMaximumAmount(event.target.value)} /></Field></div><Button className="w-full" disabled={working} onClick={() => void runAction(async () => { await lendingOperationsApi.createDecisionPolicy({ name: policyName, version: Math.max(...policies.filter((item) => item.name === policyName).map((item) => item.version), 0) + 1, status: "active", rules: { require_kyc: true, decline_on_sanctions: true, decline_on_fraud: true, minimum_credit_score: Number(minimumScore), low_score_action: "refer", maximum_dti_percent: Number(maximumDti), high_dti_action: "decline", minimum_net_income: Number(minimumIncome), maximum_loan_amount: Number(maximumAmount) }, scorecard: { base_score: 50 } }); toast.success("Active credit decision policy created."); })}><Plus className="h-4 w-4" />Create active policy version</Button></CardContent></Card>
      <Card className="rounded-3xl"><CardHeader><CardTitle>Evaluate borrower</CardTitle><CardDescription>Run the selected policy against KYC, bureau, CDAS payroll and affordability information.</CardDescription></CardHeader><CardContent className="space-y-4"><Field label="Borrower"><SearchableCombobox value={borrowerId} onValueChange={setBorrowerId} options={clientOptions} placeholder="Search borrower" /></Field><Field label="Active policy"><SearchableCombobox value={policyId} onValueChange={setPolicyId} options={activePolicies.map((item) => ({ value: item.id, label: `${item.name} v${item.version}`, description: titleCase(item.status) }))} placeholder="Select policy" /></Field><div className="grid gap-3 sm:grid-cols-2"><Field label="Requested amount"><Input className="h-11" type="number" value={requestedAmount} onChange={(event) => setRequestedAmount(event.target.value)} /></Field><Field label="Proposed instalment"><Input className="h-11" type="number" value={proposedInstallment} onChange={(event) => setProposedInstallment(event.target.value)} /></Field></div><Button className="w-full" disabled={working || !borrowerId || !policyId} onClick={() => void runAction(async () => { const result = await lendingOperationsApi.evaluateDecision({ borrower_id: borrowerId, policy_id: policyId, requested_amount: Number(requestedAmount || 0), proposed_installment: Number(proposedInstallment || 0) }); if (result.decision === "approve") toast.success(`Decision: ${titleCase(result.decision)}`); else if (result.decision === "decline") toast.error(`Decision: ${titleCase(result.decision)}`); else toast.warning(`Decision: ${titleCase(result.decision)}`); })}><SearchCheck className="h-4 w-4" />Run credit decision</Button></CardContent></Card>
    </div>
    <div className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
      <Card className="rounded-3xl"><CardHeader><CardTitle>Approval workflow designer</CardTitle><CardDescription>Create a versioned role-based approval path. This default workflow separates lending, risk, compliance and finance duties.</CardDescription></CardHeader><CardContent className="space-y-4"><Field label="Workflow name"><Input className="h-11" value={workflowName} onChange={(event) => setWorkflowName(event.target.value)} /></Field><div className="space-y-2">{["Loan officer review", "Risk assessment", "Compliance clearance", "Owner / administrator approval", "Finance disbursement"].map((step, index) => <div key={step} className="flex items-center gap-3 rounded-xl border p-3"><span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-black text-primary-foreground">{index + 1}</span><span className="text-sm font-bold">{step}</span></div>)}</div><Button className="w-full" disabled={working} onClick={() => void runAction(async () => { await lendingOperationsApi.createWorkflowTemplate({ name: workflowName, workflow_type: "loan_approval", version: Math.max(...templates.filter((item) => item.name === workflowName).map((item) => item.version), 0) + 1, status: "active", steps: [ { key: "loan_review", name: "Loan officer review", role: "loan_officer" }, { key: "risk_review", name: "Risk assessment", role: "risk_manager" }, { key: "compliance", name: "Compliance clearance", role: "compliance_officer" }, { key: "management_approval", name: "Management approval", role: "company_owner" }, { key: "finance_disbursement", name: "Finance disbursement", role: "finance_officer" } ] }); toast.success("Approval workflow template created."); })}><GitBranch className="h-4 w-4" />Create active workflow</Button></CardContent></Card>
      <Card className="rounded-3xl"><CardHeader><CardTitle>Start workflow instance</CardTitle><CardDescription>Attach the active approval path to a borrower and optional loan.</CardDescription></CardHeader><CardContent className="space-y-4"><Field label="Workflow template"><SearchableCombobox value={templateId} onValueChange={setTemplateId} options={activeTemplates.map((item) => ({ value: item.id, label: `${item.name} v${item.version}`, description: `${item.steps.length} steps` }))} placeholder="Select workflow" /></Field><Field label="Borrower"><SearchableCombobox value={borrowerId} onValueChange={setBorrowerId} options={clientOptions} placeholder="Search borrower" /></Field><Field label="Loan (optional)"><SearchableCombobox value={loanId} onValueChange={setLoanId} options={loanOptions} placeholder="Select loan" allowClear /></Field><Button className="w-full" disabled={working || !templateId || !borrowerId} onClick={() => void runAction(async () => { await lendingOperationsApi.createWorkflowInstance({ template_id: templateId, borrower_id: borrowerId, loan_id: loanId || null, context_snapshot: { source: "manual_workspace" } }); toast.success("Workflow started."); })}><Workflow className="h-4 w-4" />Start approval workflow</Button></CardContent></Card>
    </div>
    <div className="grid gap-5 xl:grid-cols-2">
      <Card className="rounded-3xl"><CardHeader><CardTitle>Recent credit decisions</CardTitle><CardDescription>Every automated result preserves the exact policy, inputs, reasons and conditions.</CardDescription></CardHeader><CardContent className="space-y-3">{decisions.map((item) => <div key={item.id} className="rounded-2xl border p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-mono text-xs font-black text-primary">{item.decision_reference}</p><p className="mt-1 text-2xl font-black">{item.score.toFixed(1)}</p></div><StatusBadge value={item.decision} /></div>{item.reasons.length ? <div className="mt-3 space-y-1 text-sm text-muted-foreground">{item.reasons.map((reason) => <p key={reason}>• {reason}</p>)}</div> : <p className="mt-3 text-sm text-emerald-700">All configured automatic checks passed.</p>}</div>)}{!decisions.length ? <EmptyState title="No credit decisions" description="Create an active policy and evaluate a borrower." /> : null}</CardContent></Card>
      <Card className="rounded-3xl"><CardHeader><CardTitle>Active workflow queue</CardTitle><CardDescription>Advance only the workflow step assigned to the currently selected role.</CardDescription></CardHeader><CardContent className="space-y-3">{instances.map((item) => <div key={item.id} className="rounded-2xl border p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-mono text-xs font-black text-primary">{item.instance_reference}</p><p className="mt-1 font-black">{item.current_step_key ? titleCase(item.current_step_key) : "Workflow complete"}</p></div><StatusBadge value={item.status} /></div><p className="mt-2 text-sm text-muted-foreground">Assigned role: {item.assigned_role ? titleCase(item.assigned_role) : "None"}</p>{item.status === "active" ? <div className="mt-3 flex gap-2"><Button className="flex-1" size="sm" disabled={working} onClick={() => void runAction(async () => { await lendingOperationsApi.advanceWorkflowInstance(item.id, { action: "approve", notes: "Approved from the lending operations workspace." }); toast.success("Workflow advanced."); })}><CheckCircle2 className="h-4 w-4" />Approve step</Button><Button className="flex-1" size="sm" variant="outline" disabled={working} onClick={() => void runAction(async () => { await lendingOperationsApi.advanceWorkflowInstance(item.id, { action: "return", notes: "Returned for correction." }); toast.warning("Workflow returned."); })}>Return</Button></div> : null}</div>)}{!instances.length ? <EmptyState title="No workflow instances" description="Start a workflow for a borrower or loan." /> : null}</CardContent></Card>
    </div>
  </>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div><p className="text-[11px] font-black uppercase tracking-wide text-muted-foreground">{label}</p><p className="mt-1 font-black">{value}</p></div>;
}

function MetricCard({ title, value, icon: Icon }: { title: string; value: string; icon: typeof Landmark }) {
  return <div className="rounded-2xl border p-4"><div className="flex items-center justify-between"><p className="text-xs font-black uppercase tracking-wide text-muted-foreground">{title}</p><Icon className="h-4 w-4 text-primary" /></div><p className="mt-3 text-2xl font-black">{value}</p></div>;
}
