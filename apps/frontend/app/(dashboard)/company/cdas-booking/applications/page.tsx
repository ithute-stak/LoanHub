"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, FilePlus2, Loader2, ShieldCheck } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { listCompanyClients } from "@/api/companyClients";
import { listLoanProducts } from "@/api/loanProducts";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { CdasApplicationHandoffItem, CdasApplicationHandoffWorkspace } from "@/types/cdasApplicationHandoff";
import type { CompanyClient } from "@/types/companyClient";
import type { LoanProduct } from "@/types/loanProduct";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

function emptyDates(term: number, current: string[] = []) {
  return Array.from({ length: Math.max(1, term) }, (_, index) => current[index] || "");
}

function safeMoney(value: number | string | null | undefined) {
  const amount = Number(value || 0);
  return new Intl.NumberFormat("en-LS", { style: "currency", currency: "LSL", maximumFractionDigits: 2 }).format(amount);
}

export default function CdasApplicationsPage() {
  const router = useRouter();
  const [workspace, setWorkspace] = useState<CdasApplicationHandoffWorkspace | null>(null);
  const [clients, setClients] = useState<CompanyClient[]>([]);
  const [products, setProducts] = useState<LoanProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<CdasApplicationHandoffItem | null>(null);
  const [borrowerId, setBorrowerId] = useState("");
  const [productId, setProductId] = useState("none");
  const [requestedAmount, setRequestedAmount] = useState(0);
  const [termCount, setTermCount] = useState(3);
  const [purpose, setPurpose] = useState("");
  const [dueDates, setDueDates] = useState<string[]>(() => emptyDates(3));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([
      cdasBookingApi.getApplicationHandoffs(),
      listCompanyClients({ status: "active", limit: 500 }),
      listLoanProducts(),
    ])
      .then(([handoffs, companyClients, loanProducts]) => {
        if (!active) return;
        setWorkspace(handoffs);
        setClients(companyClients);
        setProducts(loanProducts.filter((item) => item.is_active));
      })
      .catch((error) => toast.error(getErrorMessage(error)))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  const linkedCount = useMemo(
    () => workspace?.items.filter((item) => Boolean(item.application)).length ?? 0,
    [workspace],
  );

  function begin(item: CdasApplicationHandoffItem) {
    setSelected(item);
    setBorrowerId("");
    setProductId("none");
    setRequestedAmount(0);
    setTermCount(3);
    setPurpose("");
    setDueDates(emptyDates(3));
  }

  function updateTerm(value: number) {
    const next = Math.min(120, Math.max(1, Number(value || 1)));
    setTermCount(next);
    setDueDates((current) => emptyDates(next, current));
  }

  async function createDraft() {
    if (!selected || !borrowerId || requestedAmount <= 0 || termCount <= 0) {
      toast.error("Select the LoanHub client and enter the requested amount and term.");
      return;
    }
    if (dueDates.length !== termCount || dueDates.some((value) => !value)) {
      toast.error(`Enter all ${termCount} installment due dates.`);
      return;
    }

    setSaving(true);
    try {
      const result = await cdasBookingApi.createApplicationHandoff(selected.opportunity_id, {
        borrower_id: borrowerId,
        product_id: productId === "none" ? null : productId,
        requested_amount: requestedAmount,
        term_count: termCount,
        purpose: purpose.trim() || null,
        installment_due_dates: dueDates,
      });
      toast.success(`Draft ${result.application_reference} created.`);
      router.push(result.origination_workspace_url);
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="flex min-h-64 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin" /></div>;
  }

  return <div className="space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">CDAS → LoanHub Applications</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Turn a tracked CDAS opportunity into a traceable LoanHub origination draft, then continue through the normal KYC, affordability, approval, contract and disbursement workflow.
        </p>
      </div>
      <div className="flex gap-2">
        <Badge variant="secondary">{workspace?.total ?? 0} CDAS opportunities</Badge>
        <Badge variant="outline">{linkedCount} linked drafts</Badge>
      </div>
    </div>

    <Alert>
      <ShieldCheck className="h-4 w-4" />
      <AlertTitle>CDAS context is not a credit decision</AlertTitle>
      <AlertDescription>
        {workspace?.policy_note || "Requested amount, term, affordability, pricing and approval stay inside LoanHub origination."} The officer must choose the LoanHub client and enter the requested loan details manually.
      </AlertDescription>
    </Alert>

    {selected && !selected.application ? <Card>
      <CardHeader>
        <CardTitle className="text-lg">Create origination draft</CardTitle>
        <CardDescription>
          Source: {selected.client_name || "Unnamed CDAS client"}{selected.employer ? ` · ${selected.employer}` : ""}. Confirm the correct LoanHub client before continuing.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>LoanHub client</Label>
            <Select value={borrowerId} onValueChange={setBorrowerId}>
              <SelectTrigger><SelectValue placeholder="Select the verified company client" /></SelectTrigger>
              <SelectContent>
                {clients.map((client) => <SelectItem key={client.borrower_id} value={client.borrower_id}>
                  {client.full_name} · {client.account_reference}
                </SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Loan product (optional)</Label>
            <Select value={productId} onValueChange={setProductId}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="none">No product selected yet</SelectItem>
                {products.map((product) => <SelectItem key={product.id} value={product.id}>
                  {product.name} · {safeMoney(product.min_amount)}–{safeMoney(product.max_amount)}
                </SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Requested amount</Label>
            <Input type="number" min="0.01" step="0.01" value={requestedAmount || ""} onChange={(event) => setRequestedAmount(Number(event.target.value))} placeholder="Enter the client's requested amount" />
          </div>
          <div className="space-y-2">
            <Label>Term / number of installments</Label>
            <Input type="number" min="1" max="120" value={termCount} onChange={(event) => updateTerm(Number(event.target.value))} />
          </div>
        </div>
        <div className="space-y-2">
          <Label>Purpose (optional)</Label>
          <Textarea value={purpose} onChange={(event) => setPurpose(event.target.value)} placeholder="Record the client's stated purpose; do not copy CDAS capacity into this field." />
        </div>
        <div className="space-y-2">
          <div>
            <Label>Installment due dates</Label>
            <p className="text-xs text-muted-foreground">Enter every date explicitly. LoanHub validates the schedule again before creating the draft.</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {dueDates.map((value, index) => <div key={index} className="space-y-1">
              <Label className="text-xs">Installment {index + 1}</Label>
              <Input type="date" value={value} onChange={(event) => setDueDates((current) => current.map((row, rowIndex) => rowIndex === index ? event.target.value : row))} />
            </div>)}
          </div>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="outline" onClick={() => setSelected(null)} disabled={saving}>Cancel</Button>
          <Button onClick={createDraft} disabled={saving}>
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FilePlus2 className="mr-2 h-4 w-4" />}
            Create draft & continue
          </Button>
        </div>
      </CardContent>
    </Card> : null}

    <div className="grid gap-3">
      {(workspace?.items ?? []).map((item) => <Card key={item.opportunity_id}>
        <CardContent className="flex flex-col gap-4 p-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{item.client_name || "Unnamed CDAS client"}</span>
              <Badge variant="outline">{item.pipeline_stage || "identified"}</Badge>
              {item.application ? <Badge>Linked: {item.application.status}</Badge> : <Badge variant="secondary">Not linked</Badge>}
            </div>
            <div className="grid gap-x-6 gap-y-1 text-sm text-muted-foreground sm:grid-cols-2 xl:grid-cols-4">
              <span>Reference: {item.client_reference || "—"}</span>
              <span>Employee: {item.employee_no || "—"}</span>
              <span>Employer: {item.employer || "—"}</span>
              <span>Agency: {item.opportunity_agency_name || "—"}</span>
            </div>
            {item.application ? <p className="text-sm">
              Application <strong>{item.application.application_reference}</strong> · {safeMoney(item.application.requested_amount)} · {item.application.term_count} installments
            </p> : null}
          </div>
          <div className="shrink-0">
            {item.application ? <Button asChild>
              <Link href={`/company/origination/new?application=${item.application.id}`}>
                Continue application <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button> : <Button variant={selected?.opportunity_id === item.opportunity_id ? "secondary" : "default"} onClick={() => begin(item)}>
              Prepare LoanHub draft <ArrowRight className="ml-2 h-4 w-4" />
            </Button>}
          </div>
        </CardContent>
      </Card>)}
      {!workspace?.items.length ? <Card><CardContent className="p-8 text-center text-sm text-muted-foreground">No CDAS opportunities are available for application handoff yet.</CardContent></Card> : null}
    </div>
  </div>;
}
